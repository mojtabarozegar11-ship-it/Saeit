#!/usr/bin/env bash
# Unprivileged cron launcher: no chat reads, no messages, no QR in logs.
set -euo pipefail
umask 077
BASE="$HOME/private-messaging-bridge"
RUN="$BASE/runtime/current"
STATE="$BASE/state"
test "$#" -ge 1 || exit 2
case "$1" in
  telegram)
    [[ -s "$STATE/telegram/account.session" ]] || exit 0
    env_file="$BASE/secrets/telegram.env"
    [[ -f "$env_file" && ! -L "$env_file" ]] || exit 0
    set -a; source "$env_file"; set +a
    export MOJMSG_STATE_DIR="$STATE"
    exec /usr/bin/flock -n "$STATE/locks/telegram.lock" "$RUN/venv/bin/python" "$RUN/app/telegram.py" daemon
    ;;
  whatsapp-primary|whatsapp-secondary)
    account="$(printf '%s' "$1" | cut -d- -f2)"
    [[ -s "$STATE/whatsapp/$account/creds.json" ]] || exit 0
    export MOJMSG_STATE_DIR="$STATE"
    exec /usr/bin/flock -n "$STATE/locks/whatsapp-$account.lock" "$RUN/bin/node" "$RUN/app/whatsapp.mjs" daemon --account "$account"
    ;;
  *)
    echo "Usage: user-launch.sh telegram|whatsapp-primary|whatsapp-secondary" >&2
    exit 2
    ;;
esac