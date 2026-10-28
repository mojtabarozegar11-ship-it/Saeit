#!/usr/bin/env bash
# Private interactive pairing/status; never emit authentication keys to CI logs.
set -euo pipefail
umask 077
BASE="$HOME/private-messaging-bridge"
RUN="$BASE/runtime/current"
export MOJMSG_STATE_DIR="$BASE/state"
# For private interactive WhatsApp pairing only; never load in CI or status probes.
load_whatsapp_edge() {
  local edge_env="$BASE/secrets/whatsapp-edge.env"
  [[ -e "$edge_env" || -L "$edge_env" ]] || return 0
  [[ -f "$edge_env" && ! -L "$edge_env" ]] || return 4
  [[ "$(stat -c %u "$edge_env")" == "$(id -u)" ]] || return 4
  local edge_mode
  edge_mode="$(stat -c %a "$edge_env")"
  [[ "$edge_mode" == 600 || "$edge_mode" == 400 ]] || return 4
  set -a; source "$edge_env"; set +a
}
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
    load_whatsapp_edge
    "$RUN/bin/node" "$RUN/app/whatsapp.mjs" login --account "$account"
    ;;
  whatsapp-code)
    [[ -t 0 && -t 1 ]] || { echo 'Use a private interactive terminal for the code.' >&2; exit 2; }
    test "$#" -ge 2 || exit 2
    account="$2"
    [[ "$account" == primary || "$account" == secondary ]] || exit 2
    load_whatsapp_edge
    "$RUN/bin/node" "$RUN/app/whatsapp.mjs" login --account "$account" --pairing-code
    ;;
  whatsapp-status)
    test "$#" -ge 2 || exit 2
    account="$2"
    [[ "$account" == primary || "$account" == secondary ]] || exit 2
    "$RUN/bin/node" "$RUN/app/whatsapp.mjs" status --account "$account"
    ;;
  *)
    echo 'Use telegram-login|telegram-status|whatsapp-code [primary|secondary]|whatsapp-login [primary|secondary]|whatsapp-status [primary|secondary]' >&2
    exit 2
    ;;
esac