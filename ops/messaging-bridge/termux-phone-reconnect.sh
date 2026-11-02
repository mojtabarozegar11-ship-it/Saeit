#!/data/data/com.termux/files/usr/bin/bash
# Android Termux: check known historic keys; never upload or print any private key.
set -euo pipefail
umask 077
expected='AAAAC3NzaC1lZDI1NTE5AAAAICaXd7XWbwj/Xzr0+gyeA9nwtnqao5b62S4srHUin2C8'
mkdir -p "$HOME/.ssh"
chmod 700 "$HOME/.ssh"
for key in \
  "$HOME/.ssh/comfyui-phone" \
  "$HOME/storage/downloads/comfyui-phone-ui-key" \
  "$HOME/storage/shared/Download/comfyui-phone-ui-key" \
  "$HOME/comfyui-phone-ui-key" \
  "$HOME/Downloads/comfyui-phone-ui-key" \
  "$HOME/.ssh/comfyui_vps" \
  "$HOME/.ssh/id_ed25519" \
  "$HOME/.ssh/id_ed25519_karegar" \
  "$HOME/.ssh/saeit_termux_ed25519" \
  "$HOME/.ssh/moj_phone_recovered_ed25519"; do
  [[ -f "$key" && ! -L "$key" ]] || continue
  probe="$key"
  temp=''
  if [[ "$key" != "$HOME/.ssh/"* ]]; then
    # Android shared storage can expose unsafe file permissions; inspect via private copy.
    temp="$(mktemp "$HOME/.ssh/.moj-phone-inspect.XXXXXX")"
    if ! cp -- "$key" "$temp"; then rm -f -- "$temp"; continue; fi
    chmod 600 "$temp"
    probe="$temp"
  else
    chmod 600 "$probe" 2>/dev/null || true
  fi
  derived="$(ssh-keygen -y -P '' -f "$probe" 2>/dev/null | awk '{print $2}' || true)"
  if [[ "$derived" != "$expected" ]]; then
    [[ -z "$temp" ]] || rm -f -- "$temp"
    continue
  fi
  chosen="$key"
  if [[ -n "$temp" ]]; then
    chosen="$HOME/.ssh/moj_phone_recovered_ed25519"
    if [[ -e "$chosen" || -L "$chosen" ]]; then
      existing="$(ssh-keygen -y -P '' -f "$chosen" 2>/dev/null | awk '{print $2}' || true)"
      rm -f -- "$temp"
      if [[ "$existing" != "$expected" ]]; then
        echo 'An unrelated recovered key exists; will not overwrite it.' >&2
        exit 3
      fi
    else
      mv -- "$temp" "$chosen"
    fi
  fi
  chmod 600 "$chosen" 2>/dev/null || true
  echo "Found original registered phone key: $chosen"
  echo 'Connecting directly to private Telegram/WhatsApp wizard.'
  exec ssh -tt -o IdentitiesOnly=yes -o PasswordAuthentication=no -i "$chosen" githubops@178.239.147.150
done
newkey="$HOME/.ssh/moj_messaging_phone_ed25519"
if [[ ! -e "$newkey" && ! -L "$newkey" ]]; then
  ssh-keygen -q -t ed25519 -N '' -C 'moj-messaging-phone-20261028' -f "$newkey"
  chmod 600 "$newkey"
  echo 'Original key not found. Created a new key on your phone only.'
else
  echo 'Original key not found. Your existing replacement key was not overwritten.'
fi
if [[ -f "$newkey.pub" && ! -L "$newkey.pub" ]]; then
  echo 'Share only the following PUBLIC key in ChatGPT so its VPS permission can be installed:'
  cat "$newkey.pub"
else
  echo 'Replacement key exists but no public half is available; no existing files were replaced.' >&2
  exit 4
fi
