#!/usr/bin/env bash
# Private Tailscale Serve for the existing ComfyUI CPU runtime, no sudo / no Funnel.
# Run as githubops over the pinned GitHub Actions SSH transport.
set -Eeuo pipefail
umask 077
mode="${1:-status}"
case "$mode" in status|connect|disconnect) ;; *) echo PRIVATE_TAILNET_INVALID_MODE; exit 2 ;; esac

root="$HOME/.local/opt/comfyui-tailnet"
bin="$root/binaries-1.104.1"
state="$HOME/.local/share/comfyui-tailnet"
sock="$state/tailscaled.sock"
pidfile="$state/tailscaled.pid"
log="$state/tailscaled.log"
auth="$state/authkey.pending"
test "$(id -un)" = githubops || { echo PRIVATE_TAILNET_WRONG_USER; exit 3; }
test -x "$bin/tailscale" && test -x "$bin/tailscaled" || { echo PRIVATE_TAILNET_BINARIES_MISSING; exit 3; }
install -d -m 700 "$state"
exec 9>"$state/control.lock"
flock -w 12 9 || { echo PRIVATE_TAILNET_BUSY; exit 4; }
ts() { "$bin/tailscale" --socket="$sock" "$@"; }
ours() {
  local pid
  [[ -r "$pidfile" ]] || return 1
  read -r pid < "$pidfile" || return 1
  [[ "$pid" =~ ^[0-9]+$ && -r "/proc/$pid/cmdline" ]] || return 1
  grep -azFq -- "$bin/tailscaled" "/proc/$pid/cmdline" || return 1
  grep -azFq -- "$sock" "/proc/$pid/cmdline" || return 1
}
state_value() {
  ts status --json 2>/dev/null | python3 -c 'import json,sys; j=json.load(sys.stdin); print(j.get("BackendState","UNKNOWN"))'
}
start_daemon() {
  if ours; then return 0; fi
  if [[ -S "$sock" ]]; then
    echo PRIVATE_TAILNET_EXISTING_UNTRACKED_SOCKET_REFUSE
    exit 5
  fi
  nohup "$bin/tailscaled" \
    --tun=userspace-networking \
    --socket="$sock" \
    --state="$state/tailscaled.state" \
    --statedir="$state" \
    --no-logs-no-support \
    </dev/null >>"$log" 2>&1 9>&- &
  pid=$!
  printf '%s\n' "$pid" > "$pidfile"
  for _ in $(seq 1 25); do
    if [[ -S "$sock" ]] && ts status --json >/dev/null 2>&1; then
      echo PRIVATE_TAILNET_USERSPACE_DAEMON_READY
      return 0
    fi
    if ! kill -0 "$pid" 2>/dev/null; then break; fi
    sleep 1
  done
  echo PRIVATE_TAILNET_DAEMON_FAILED
  if ours; then kill -TERM "$pid" 2>/dev/null || true; fi
  rm -f "$pidfile"
  exit 6
}
case "$mode" in
  status)
    if ours; then
      echo PRIVATE_TAILNET_DAEMON_RUNNING
      backend="$(state_value || true)"
      case "$backend" in
        Running) echo PRIVATE_TAILNET_AUTHENTICATED ;;
        NeedsLogin|NoState) echo PRIVATE_TAILNET_REQUIRES_AUTHENTICATION ;;
        *) echo "PRIVATE_TAILNET_BACKEND_OTHER" ;;
      esac
      if ts serve status --json >/dev/null 2>&1; then echo PRIVATE_TAILNET_SERVE_STATUS_READABLE; fi
    else
      echo PRIVATE_TAILNET_DAEMON_NOT_RUNNING
    fi
    ;;
  connect)
    [[ -f "$auth" && ! -L "$auth" && -s "$auth" ]] || { echo PRIVATE_TAILNET_AUTHKEY_NOT_CONFIGURED; exit 7; }
    chmod 600 "$auth"
    trap 'rm -f -- "$auth"' EXIT
    start_daemon
    # The file: form avoids putting auth keys in process command-line arguments.
    timeout 45s ts up --auth-key="file:$auth" --hostname=comfyui-private-vps --accept-routes=false >/dev/null
    backend="$(state_value)"
    [[ "$backend" == Running ]] || { echo PRIVATE_TAILNET_AUTHENTICATION_FAILED; exit 8; }
    echo PRIVATE_TAILNET_AUTHENTICATED
    # Serve is private to tailnet; never run 'tailscale funnel'.
    timeout 40s ts serve --yes --bg --https=443 http://127.0.0.1:18188 >/dev/null
    echo PRIVATE_COMFYUI_TAILNET_HTTPS_CONFIGURED
    echo PUBLIC_COMFYUI_PORT_NOT_OPENED
    ;;
  disconnect)
    if ours; then
      ts serve --https=443 off >/dev/null 2>&1 || true
      localpid="$(cat "$pidfile")"
      kill -TERM "$localpid" 2>/dev/null || true
      rm -f "$pidfile"
      echo PRIVATE_TAILNET_DAEMON_STOP_SIGNAL_SENT
    else
      echo PRIVATE_TAILNET_ALREADY_IDLE
    fi
    ;;
esac
