#!/usr/bin/env bash
# Read-only staging connectivity and deployment-readiness probe.
set -Eeuo pipefail
: "${STAGING_SSH_KEY:?Missing STAGING_SSH_KEY}"
: "${KNOWN_HOSTS:?Missing KNOWN_HOSTS}"
SSH_HOST="zohal.pws-dns.net"
SSH_PORT="1396"
SSH_USER="zomorod2"
STAGING_DIR="/home/zomorod2/Saeit-staging"
umask 077
workdir="$(mktemp -d)"
trap 'rm -rf "$workdir"' EXIT
printf '%s\n' "$STAGING_SSH_KEY" > "$workdir/id_ed25519"
printf '%s\n' "$KNOWN_HOSTS" > "$workdir/known_hosts"
chmod 600 "$workdir/id_ed25519" "$workdir/known_hosts"
# Refuse to proceed unless the pinned host key is present.
ssh-keygen -F "[$SSH_HOST]:$SSH_PORT" -f "$workdir/known_hosts" >/dev/null || {
  echo "FAIL: missing pinned host key for [$SSH_HOST]:$SSH_PORT" >&2; exit 2;
}
ssh -F /dev/null -i "$workdir/id_ed25519" -o IdentitiesOnly=yes -o BatchMode=yes \
  -o StrictHostKeyChecking=yes -o UserKnownHostsFile="$workdir/known_hosts" \
  -o ConnectTimeout=12 -p "$SSH_PORT" "$SSH_USER@$SSH_HOST" \
  "test -d '$STAGING_DIR' && test -r '$STAGING_DIR' && printf 'STAGING_READABLE\\n' && test -d '$STAGING_DIR/.git' && printf 'STAGING_GIT_PRESENT\\n'"
echo "PASS: read-only staging SSH check completed. No deployment was performed."
