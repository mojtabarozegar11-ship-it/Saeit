#!/usr/bin/env bash
# One-time LOCAL interactive pairing. Never display Telegram credentials/OTP publicly.
# This is not a ChatGPT messaging connector; it only authenticates private VPS keepers.
set -euo pipefail
umask 077
if [[ ! -t 0 || ! -t 1 ]]; then
  echo 'Open this script in your own private SSH terminal (not GitHub Actions).' >&2
  exit 2
fi
BASE="$HOME/private-messaging-bridge"
CONTROL="$BASE/runtime/current/app/user-control.sh"
STATE="$BASE/state"
[[ "$(id -un)" == githubops && -f "$CONTROL" && ! -L "$BASE" ]] || { echo 'Wrong account or bridge not installed.' >&2; exit 2; }
mkdir -p -m 0700 "$BASE/secrets"
chmod 0700 "$BASE/secrets"
printf '\nPRIVATE MESSAGING SETUP — one-time sign-in on your own VPS\n'
printf 'No authentication code, API hash, QR token or chat is saved to GitHub or sent to ChatGPT.\n'
printf 'You can skip Telegram and set it up later if you do not have API credentials.\n\n'
if [[ -s "$STATE/telegram/account.session" ]]; then
  printf 'Telegram saved session exists; keeping it. No new login requested.\n'
else
  tgenv="$BASE/secrets/telegram.env"
  if [[ ! -f "$tgenv" ]]; then
    printf 'Telegram developer API credentials are obtained at https://my.telegram.org/apps\n'
    read -r -p 'Telegram API ID (Enter to skip Telegram): ' api_id
    if [[ -n "$api_id" ]]; then
      if [[ ! "$api_id" =~ ^[0-9]{4,15}$ ]]; then
        echo 'Invalid API ID. Telegram skipped.' >&2
      else
        read -r -s -p 'Telegram API HASH (hidden): ' api_hash
        echo
        if [[ "$api_hash" =~ ^[a-fA-F0-9]{32}$ ]]; then
          [[ ! -L "$tgenv" ]] || { echo 'Unsafe Telegram config symlink.' >&2; exit 3; }
          ( set -C; printf 'TG_API_ID=%s\nTG_API_HASH=%s\n' "$api_id" "$api_hash" > "$tgenv" )
          chmod 0600 "$tgenv"
          echo 'Telegram credentials saved privately in 0600 mode.'
        else
          echo 'Invalid API HASH format; no credentials written.' >&2
        fi
        unset api_hash
      fi
    fi
  fi
  if [[ -f "$tgenv" && ! -L "$tgenv" ]]; then
    echo 'Telegram phone sign-in starts in this private terminal; enter codes only here.'
    if "$CONTROL" telegram-login; then
      echo 'Telegram session saved. Background reconnect will start automatically.'
    else
      echo 'Telegram not paired; no other account was modified.' >&2
    fi
  fi
fi

for account in primary secondary; do
  if [[ -s "$STATE/whatsapp/$account/creds.json" ]]; then
    printf 'WhatsApp %s has saved device authorization; not requesting it again.\n' "$account"
    continue
  fi
  if [[ "$account" == secondary ]]; then
    read -r -p 'Link a second WhatsApp account too? [y/N]: ' consent
    case "$consent" in y|Y|yes|YES) ;; *) continue ;; esac
  fi
  printf '\nWhatsApp %s: a short pairing code will be displayed here; not a QR.\n' "$account"
  printf 'On that phone: WhatsApp > Linked devices > Link a device > Link with phone number instead.\n'
  if "$CONTROL" whatsapp-code "$account"; then
    echo "WhatsApp $account pairing succeeded and private credentials were saved."
  else
    echo "WhatsApp $account was not paired; retry in private terminal if needed." >&2
  fi
done

printf '\nSaved state (these are local status markers; daemon health changes after cron starts):\n'
"$CONTROL" telegram-status || :
"$CONTROL" whatsapp-status primary || :
"$CONTROL" whatsapp-status secondary || :
printf '\nThe cron keepers use the saved session keys and do not require QR/code on every reconnect.\n'
printf 'Provider logout/revocation can require you to authorize again. ChatGPT access is a separate integration.\n'