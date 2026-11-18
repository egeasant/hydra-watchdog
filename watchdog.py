import argparse
import json
import logging
import socket
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
from rich.console import Console
from rich.table import Table

console = Console()

logging.basicConfig(
    filename="watchdog.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def load_config(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        console.print(f"[bold red]Erro:[/] Arquivo '{config_path}' não encontrado.")
        console.print("Copie 'config.example.json' para 'config.json' e preencha seus dados.")
        sys.exit(1)

    with config_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def check_tcp_port(target: dict[str, Any], timeout: float) -> dict[str, Any]:
    host = target["host"]
    port = int(target["port"])
    start_time = time.perf_counter()

    try:
        with socket.create_connection((host, port), timeout=timeout):
            latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
            return {**target, "online": True, "latency_ms": latency_ms, "error": None}
    except socket.timeout:
        return {**target, "online": False, "latency_ms": None, "error": "Timeout"}
    except ConnectionRefusedError:
        return {**target, "online": False, "latency_ms": None, "error": "Conexão recusada"}
    except OSError as exc:
        return {**target, "online": False, "latency_ms": None, "error": str(exc)}


def send_discord_alert(webhook_url: str, result: dict[str, Any], is_recovery: bool) -> None:
    if not webhook_url or "SEU_WEBHOOK" in webhook_url:
        return

    timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    if is_recovery:
        title = f"✅ SERVIÇO RESTABELECIDO: {result['name']}"
        color = 3066993  # Verde
        status_text = f"Online ({result['latency_ms']} ms)"
    else:
        title = f"🚨 ALERTA DE QUEDA: {result['name']}"
        color = 15158332  # Vermelho
        status_text = f"Offline ({result['error']})"

    payload = {
        "username": "Hydra Watchdog",
        "embeds": [
            {
                "title": title,
                "color": color,
                "fields": [
                    {"name": "Categoria", "value": result.get("category", "Geral"), "inline": True},
                    {"name": "Endpoint", "value": f"`{result['host']}:{result['port']}`", "inline": True},
                    {"name": "Status", "value": status_text, "inline": False},
                ],
                "footer": {"text": f"Detectado em {timestamp}"},
            }
        ],
    }

    try:
        response = requests.post(webhook_url, json=payload, timeout=5)
        response.raise_for_status()
    except requests.RequestException as exc:
        logging.error(f"Falha ao enviar alerta para o Discord: {exc}")


def send_telegram_alert(bot_token: str, chat_id: str, result: dict[str, Any], is_recovery: bool) -> None:
    if not bot_token or not chat_id:
        return

    timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    if is_recovery:
        header = f"✅ *SERVIÇO RESTABELECIDO*\n"
        detail = f"*Status:* Online ({result['latency_ms']} ms)"
    else:
        header = f"🚨 *ALERTA DE QUEDA*\n"
        detail = f"*Motivo:* {result['error']}"

    message = (
        f"{header}"
        f"*Serviço:* {result['name']}\n"
        f"*Categoria:* {result.get('category', 'Geral')}\n"
        f"*Endpoint:* `{result['host']}:{result['port']}`\n"
        f"{detail}\n"
        f"*Horário:* {timestamp}"
    )

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}

    try:
        response = requests.post(url, json=payload, timeout=5)
        response.raise_for_status()
    except requests.RequestException as exc:
        logging.error(f"Falha ao enviar alerta para o Telegram: {exc}")


def dispatch_notifications(notifications: dict[str, str], result: dict[str, Any], is_recovery: bool) -> None:
    discord_url = notifications.get("discord_webhook_url", "")
    tg_token = notifications.get("telegram_bot_token", "")
    tg_chat = notifications.get("telegram_chat_id", "")

    if discord_url:
        send_discord_alert(discord_url, result, is_recovery)
    if tg_token and tg_chat:
        send_telegram_alert(tg_token, tg_chat, result, is_recovery)


def render_table(results: list[dict[str, Any]]) -> None:
    now = datetime.now().strftime("%H:%M:%S")
    table = Table(title=f"Hydra Watchdog — Status de Infraestrutura ({now})")

    table.add_column("Categoria", style="cyan", no_wrap=True)
    table.add_column("Serviço", style="bold white")
    table.add_column("Endpoint", style="magenta")
    table.add_column("Status", justify="center")
    table.add_column("Latência / Detalhe", justify="right")

    for res in results:
        endpoint = f"{res['host']}:{res['port']}"
        if res["online"]:
            status = "[bold green]ONLINE[/]"
            detail = f"{res['latency_ms']} ms"
        else:
            status = "[bold red]OFFLINE[/]"
            detail = f"[red]{res['error']}[/]"

        table.add_row(res.get("category", "-"), res["name"], endpoint, status, detail)

    console.print(table)


def run_cycle(
    targets: list[dict[str, Any]],
    timeout: float,
    max_workers: int,
    state_cache: dict[str, bool],
    notifications: dict[str, str],
) -> list[dict[str, Any]]:
    results = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(check_tcp_port, target, timeout): target for target in targets}
        for future in as_completed(futures):
            res = future.result()
            results.append(res)

            key = f"{res['host']}:{res['port']}"
            current_status = res["online"]
            previous_status = state_cache.get(key, True)

            if not current_status and previous_status:
                logging.warning(f"QUEDA DETECTADA: {res['name']} ({key}) - {res['error']}")
                dispatch_notifications(notifications, res, is_recovery=False)
            elif current_status and not previous_status:
                logging.info(f"SERVIÇO NORMALIZADO: {res['name']} ({key}) - {res['latency_ms']}ms")
                dispatch_notifications(notifications, res, is_recovery=True)

            state_cache[key] = current_status

    # Mantém a ordenação original do config.json na exibição
    order_map = {f"{t['host']}:{t['port']}": idx for idx, t in enumerate(targets)}
    results.sort(key=lambda x: order_map.get(f"{x['host']}:{x['port']}", 999))
    return results


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Hydra Watchdog — Monitor de disponibilidade TCP para ERPs, Bancos de Dados e CFTV."
    )
    parser.add_argument(
        "-c", "--config", type=Path, default=Path("config.json"), help="Caminho para o arquivo JSON de configuração."
    )
    parser.add_argument(
        "--once", action="store_true", help="Executa apenas uma varredura e encerra (ideal para testes ou Cron)."
    )
    args = parser.parse_args()

    config = load_config(args.config)
    settings = config.get("settings", {})
    notifications = config.get("notifications", {})
    targets = config.get("targets", [])

    if not targets:
        console.print("[yellow]Nenhum alvo configurado em 'targets'. Encerrando.[/]")
        sys.exit(0)

    interval = int(settings.get("interval_seconds", 60))
    timeout = float(settings.get("timeout_seconds", 3.0))
    max_workers = int(settings.get("max_workers", 10))
    state_cache: dict[str, bool] = {}

    logging.info("Hydra Watchdog iniciado.")

    try:
        while True:
            results = run_cycle(targets, timeout, max_workers, state_cache, notifications)
            render_table(results)

            if args.once:
                break

            time.sleep(interval)
    except KeyboardInterrupt:
        console.print("\n[bold yellow]Monitoramento interrompido pelo usuário.[/]")
        logging.info("Hydra Watchdog encerrado manualmente.")


if __name__ == "__main__":
    main()