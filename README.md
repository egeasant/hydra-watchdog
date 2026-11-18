# 🛡️ Hydra Watchdog

Daemon leve em Python para monitoramento contínuo de disponibilidade de serviços críticos via TCP Socket, desenvolvido para ambientes de infraestrutura, servidores de ERP/PDV, bancos de dados e sistemas de CFTV (DVR/NVR).

## ⚡ Funcionalidades

- **Verificação Paralela:** Utiliza `ThreadPoolExecutor` para testar múltiplos hosts simultaneamente sem bloqueios por timeout.
- **Gestão Inteligente de Estado (Anti-Spam):** Dispara alertas críticos apenas no momento da queda (`ONLINE → OFFLINE`) e envia notificação de recuperação quando o serviço volta (`OFFLINE → ONLINE`).
- **Alertas Multi-Plataforma:** Suporte nativo a **Discord** (via Embeds ricos) e **Telegram** (via Bot API).
- **Métricas de Latência:** Mede o tempo de resposta do handshake TCP em milissegundos (`ms`).
- **Modo CLI & Daemon:** Permite execução única (`--once`) para diagnóstico rápido no terminal ou loop contínuo com logs persistentes em `watchdog.log`.

## 🛠️ Instalação

```bash
git clone [https://github.com/egeasant/Hydra-Watchdog.git](https://github.com/egeasant/Hydra-Watchdog.git)
cd Hydra-Watchdog
python -m venv .venv
source .venv/bin/activate  # No Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## ⚙️ Configuração

1. Duplique o arquivo de exemplo:
```bash
cp config.example.json config.json
```

2. Edite o `config.json` inserindo sua URL de Webhook do Discord (ou Token/Chat ID do Telegram) e os endpoints que deseja monitorar:

```json
{
  "settings": {
    "interval_seconds": 60,
    "timeout_seconds": 3.0,
    "max_workers": 10
  },
  "notifications": {
    "discord_webhook_url": "[https://discord.com/api/webhooks/](https://discord.com/api/webhooks/)...",
    "telegram_bot_token": "",
    "telegram_chat_id": ""
  },
  "targets": [
    {
      "name": "Servidor ERP - Firebird",
      "host": "192.168.1.10",
      "port": 3050,
      "category": "Banco de Dados"
    }
  ]
}
```

## 🚀 Uso

**Executar diagnóstico único no terminal:**
```bash
python watchdog.py --once
```

**Iniciar monitoramento contínuo:**
```bash
python watchdog.py
```

**Especificar um arquivo de configuração customizado:**
```bash
python watchdog.py -c /etc/hydra-watchdog/cliente_a.json
```

## 👨‍💻 Autor

Desenvolvido por **Nicolas Egea dos Santos** ([@egeasant](https://github.com/egeasant)).
