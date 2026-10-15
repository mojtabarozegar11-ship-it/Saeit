#!/data/data/com.termux/files/usr/bin/bash
# SSH-forward ONLY the VPS's localhost-bound ComfyUI canvas to this phone.
# Nothing is published on an Internet interface. Run directly inside Termux.
set -Eeuo pipefail
umask 077

VPS_HOST=178.239.147.150
VPS_USER=githubops
REMOTE_PORT=18188
LOCAL_PORT=18189
PIN='SHA256:AYdzF3K5uSwAXElE1w/dKo04iT2BbMGwHbRA2Cu4rrs'
ROOT="$HOME/.saeit-comfyui-phone"
KEY="$ROOT/comfyui_ed25519"
KNOWN="$ROOT/known_hosts"
mode="${1:-help}"

if [[ "${PREFIX:-}" != /data/data/com.termux/files/usr* ]]; then
  echo 'TERMUX_ENVIRONMENT_REQUIRED'
  exit 2
fi
case "$mode" in
  prepare)
    command -v ssh-keygen >/dev/null || { echo 'INSTALL_OPENSSH_IN_TERMUX_FIRST'; exit 3; }
    install -d -m 700 "$ROOT"
    [[ ! -L "$KEY" && ! -L "$KEY.pub" ]] || { echo 'REFUSE_SYMLINK'; exit 4; }
    if [[ ! -f "$KEY" ]]; then
      ssh-keygen -q -t ed25519 -N '' -C 'saeit-comfyui-mobile-v1' -f "$KEY"
    fi
    chmod 600 "$KEY"
    echo 'PUBLIC_KEY_ONLY_COPY_TO_GITHUB_ACTIONS_AUTHORIZE:'
    cat "$KEY.pub"
    echo 'PRIVATE_KEY_REMAINS_ON_PHONE'
    ;;
  connect)
    command -v ssh >/dev/null && command -v ssh-keyscan >/dev/null || { echo 'INSTALL_OPENSSH_IN_TERMUX_FIRST'; exit 3; }
    test -f "$KEY" && test -f "$KEY.pub" || { echo 'RUN_PREPARE_FIRST'; exit 5; }
    install -d -m 700 "$ROOT"
    [[ ! -L "$KNOWN" ]] || { echo 'REFUSE_SYMLINK'; exit 4; }
    temp="$(mktemp "$ROOT/.known-XXXXXX")"
    trap 'rm -f -- "$temp"' EXIT
    ssh-keyscan -T 12 -p 22 -t rsa "$VPS_HOST" > "$temp" 2>/dev/null || { echo 'VPS_SSH_UNREACHABLE'; exit 6; }
    [[ "$(ssh-keygen -lf "$temp" -E sha256 | awk '{print $2}' | sort -u)" == "$PIN" ]] || { echo 'VPS_HOST_KEY_CHANGED_REFUSE'; exit 7; }
    mv -f -- "$temp" "$KNOWN"
    chmod 600 "$KNOWN"
    echo "OPEN_PHONE_BROWSER: http://127.0.0.1:$LOCAL_PORT"
    echo 'SSH_TUNNEL_FOREGROUND_CTRL_C_TO_STOP'
    exec ssh -N -T -i "$KEY" -p 22 \
      -L "127.0.0.1:$LOCAL_PORT:127.0.0.1:$REMOTE_PORT" \
      -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=yes \
      -o UserKnownHostsFile="$KNOWN" -o ExitOnForwardFailure=yes \
      -o ServerAliveInterval=30 -o ServerAliveCountMax=3 \
      -o ConnectTimeout=15 "$VPS_USER@$VPS_HOST"
    ;;
  health)
    command -v curl >/dev/null || { echo 'CURL_REQUIRED'; exit 3; }
    if curl -fsS -m 7 -o /dev/null "http://127.0.0.1:$LOCAL_PORT/system_stats"; then
      echo 'COMFYUI_PRIVATE_MOBILE_GUI_HEALTHY'
    else
      echo 'COMFYUI_GUI_NOT_CONNECTED_OR_SESSION_STOPPED'
      exit 1
    fi
    ;;
  *)
    echo 'Usage: bash termux-local-gui.sh prepare|connect|health'
    exit 2
    ;;
esac
