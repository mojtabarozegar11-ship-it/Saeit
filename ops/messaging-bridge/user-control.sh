#!/usr/bin/env bash
# Private interactive pairing/status; never emit authentication keys to CI logs.
set -euo pipefail
umask 077
BASE="$HOME/private-messaging-bridge"
RUN="$BASE/runtime/current"
export MOJMSG_STATE_DIR="$BASE/state"
test "$#" -ge 1 || exit 2
case "$1" in
  telegram-login)
    [[ -t 0 && -t 1 ]] || { echo 'Use a private interactive terminal, not GitHub Actions.' >&2; exit 2; }
    file="$BASE/secrets/telegram.env"
    [[ -f "$file" && ! -L "$file" ]] || { echo 'Configure private secrets/telegram.env first.' >&2; exit 2; }
    set -a; source "$file"; set +a
    "$RUN/venv/bin/python" "$RUN/app/telegram.py" login
    ;;
  telegram-status)
    "$RUN/venv/bin/python" "$RUN/app/telegram.py" status
    ;;
  whatsapp-login)
    [[ -t 0 && -t 1 ]] || { echo 'Use a private interactive terminal to display QR.' >&2; exit 2; }
    test "$#" -ge 2 || exit 2
    account="$2"
    [[ "$account" == primary || "$account" == secondary ]] || exit 2
    "$RUN/bin/node" "$RUN/app/whatsapp.mjs" login --account "$account"
    ;;
  whatsapp-status)
    test "$#" -ge 2 || exit 2
    account="$2"
    [[ "$account" == primary || "$account" == secondary ]] || exit 2
    "$RUN/bin/node" "$RUN/app/whatsapp.mjs" status --account "$account"
    ;;
  *)
    echo 'Use telegram-login|telegram-status|whatsapp-login [primary|secondary]|whatsapp-status [primary|secondary]' >&2
    exit 2
    ;;
esac