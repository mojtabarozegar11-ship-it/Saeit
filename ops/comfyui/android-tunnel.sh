#!/usr/bin/env bash
# Termux / Android SSH tunnel for private ComfyUI.
# This script never sends the private key to GitHub or the VPS.
set -euo pipefail
umask 077

host="178.239.147.150"
account="githubops"
key="$HOME/.ssh/comfyui_vps"
known="$HOME/.ssh/comfyui_vps_known_hosts"
expected="SHA256:AYdzF3K5uSwAXElE1w/dKo04iT2BbMGwHbRA2Cu4rrs"
mode="$(printf '%s' "setup")"
if (( $# > 0 )); then mode="$1"; fi

command -v ssh >/dev/null || { echo "Termux OpenSSH is missing. Run: pkg install openssh"; exit 1; }
install -d -m 700 "$HOME/.ssh"

case "$mode" in
  setup)
    command -v ssh-keygen >/dev/null || { echo "Missing ssh-keygen"; exit 1; }
    if test -e "$key" || test -e "$key.pub"; then
      test -s "$key" && test -s "$key.pub" || { echo "KEY_PAIR_INCOMPLETE. Inspect it; no key was overwritten."; exit 1; }
      echo "EXISTING_PHONE_KEY_REUSED"
    else
      ssh-keygen -t ed25519 -a 64 -f "$key" -N "" -C "comfyui-android-tunnel"
      echo "NEW_PHONE_KEY_CREATED"
    fi
    chmod 600 "$key"
    echo "PHONE_PUBLIC_KEY_ONLY:"
    cat "$key.pub"
    echo "Do not share $key (the private key)."
    echo "Wait until this public key is authorized with forwarding-only restrictions on the VPS."
    ;;
  connect)
    test -s "$key" && test -s "$key.pub" || { echo "Run: bash android-tunnel.sh setup"; exit 1; }
    command -v ssh-keyscan >/dev/null || { echo "Missing ssh-keyscan"; exit 1; }
    scan="$(ssh-keyscan -T 10 -t rsa "$host" 2>/dev/null)"
    test -n "$scan" || { echo "HOST_KEY_SCAN_FAILED"; exit 1; }
    actual="$(printf '%s\n' "$scan" | ssh-keygen -lf - -E sha256 | awk '{print $2}' | sort -u)"
    if test "$actual" != "$expected"; then
      echo "HOST_KEY_FINGERPRINT_MISMATCH: refusing connection."
      exit 1
    fi
    tmp="$(mktemp "$HOME/.ssh/.comfy-hostkey.XXXXXXXX")"
    trap 'rm -f -- "$tmp"' EXIT
    printf '%s\n' "$scan" > "$tmp"
    chmod 600 "$tmp"
    mv -f -- "$tmp" "$known"
    trap - EXIT
    echo "HOST_KEY_VERIFIED"
    echo "This terminal stays open while the tunnel is active."
    echo "On the phone, open: http://127.0.0.1:18188"
    exec ssh \
      -i "$key" \
      -p 22 \
      -o IdentitiesOnly=yes \
      -o PreferredAuthentications=publickey \
      -o PasswordAuthentication=no \
      -o BatchMode=yes \
      -o StrictHostKeyChecking=yes \
      -o UserKnownHostsFile="$known" \
      -o ExitOnForwardFailure=yes \
      -o ServerAliveInterval=30 \
      -o ServerAliveCountMax=2 \
      -o ForwardAgent=no \
      -T -N \
      -L 127.0.0.1:18188:127.0.0.1:18188 \
      "$account@$host"
    ;;
  *)
    echo "Usage: bash android-tunnel.sh setup | connect"
    exit 2
    ;;
esac
