#!/usr/bin/env bash
# SSH forced-command gate for the previously installed PHONE key only.
# No interactive shell, no arbitrary remote command, no public QR or log.
set -euo pipefail
umask 077

if [[ "$(id -un)" != "githubops" || "$HOME" != "/home/githubops" ]]; then
  echo 'ACCESS_DENIED_WRONG_ACCOUNT' >&2
  exit 126
fi
# OpenSSH populates SSH_ORIGINAL_COMMAND for remote exec, scp and sftp.
# The user is permitted a TTY-only sign-in *without* a remote command.
if [[ -v SSH_ORIGINAL_COMMAND && -n "$SSH_ORIGINAL_COMMAND" ]]; then
  echo 'ACCESS_DENIED_REMOTE_COMMAND' >&2
  exit 126
fi
if [[ ! -t 0 || ! -t 1 ]]; then
  echo 'This key only opens the private Telegram/WhatsApp onboarding in an interactive SSH terminal.' >&2
  exit 126
fi
if [[ ! -v SSH_CONNECTION || -z "$SSH_CONNECTION" ]]; then
  echo 'ACCESS_DENIED_NOT_SSH' >&2
  exit 126
fi

base="$HOME/private-messaging-bridge"
onboard="$base/runtime/current/app/user-onboard.sh"
if [[ ! -x "$onboard" || -L "$base" || -L "$base/runtime" ]]; then
  echo 'The private onboarding is not installed or its paths are unsafe.' >&2
  exit 127
fi
# Reset environment before executing the pre-approved bounded onboarding script.
# Retain the real SSH TTY streams for direct phone verification by the owner.
exec /usr/bin/env -i \
  HOME="/home/githubops" \
  USER="githubops" \
  LOGNAME="githubops" \
  PATH="/usr/local/bin:/usr/bin:/bin" \
  TERM="xterm-256color" \
  SSH_CONNECTION="$SSH_CONNECTION" \
  /usr/bin/bash --noprofile --norc "$onboard"
