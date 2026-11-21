#!/usr/bin/env bash
set -euo pipefail
[[ "$(id -u)" == 0 ]] || { echo 'Run with sudo' >&2; exit 2; }
ROOT=/opt/moj-messaging
ENV_FILE=/etc/moj-messaging/bridge.env
case "${1:-}" in
  telegram-login)
    [[ -f "$ENV_FILE" ]] || { echo 'Create private bridge.env first'; exit 2; }
    set -a; source "$ENV_FILE"; set +a
    runuser -u mojmsg -- "$ROOT/.venv/bin/python" "$ROOT/telegram.py" login ;;
  telegram-status)
    set -a; source "$ENV_FILE"; set +a
    runuser -u mojmsg -- "$ROOT/.venv/bin/python" "$ROOT/telegram.py" status ;;
  whatsapp-login)
    name="${2:-primary}"
    [[ "$name" =~ ^[a-z][a-z0-9_-]{0,30}$ ]] || exit 2
    runuser -u mojmsg -- /usr/bin/env node "$ROOT/whatsapp.mjs" login --account "$name" ;;
  whatsapp-status)
    name="${2:-primary}"
    [[ "$name" =~ ^[a-z][a-z0-9_-]{0,30}$ ]] || exit 2
    runuser -u mojmsg -- /usr/bin/env node "$ROOT/whatsapp.mjs" status --account "$name" ;;
  *) echo 'Usage: control.sh telegram-login|telegram-status|whatsapp-login|whatsapp-status [primary|secondary]' >&2; exit 2 ;;
esac