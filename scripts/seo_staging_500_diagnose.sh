#!/usr/bin/env bash
# Read-only staging HTTP 500 triage. Never prints environment values, secrets or logs.
set -Eeuo pipefail
: "${STAGING_SSH_KEY:?STAGING_SSH_KEY missing}"
: "${KNOWN_HOSTS:?KNOWN_HOSTS missing}"
umask 077
d="$(mktemp -d)"
trap 'rm -rf "$d"' EXIT
printf '%s\n' "$STAGING_SSH_KEY" > "$d/id"
printf '%s\n' "$KNOWN_HOSTS" > "$d/known_hosts"
chmod 600 "$d/id" "$d/known_hosts"
ssh-keygen -F '[zohal.pws-dns.net]:1396' -f "$d/known_hosts" >/dev/null
ssh -F /dev/null -p 1396 -i "$d/id" -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile="$d/known_hosts" -o ConnectTimeout=12 zomorod2@zohal.pws-dns.net 'bash -s' <<'REMOTE'
set -u
p=/home/zomorod2/Saeit-staging
echo "STAGING_DIR=$([ -d "$p" ] && echo present || echo missing)"
echo "STAGING_MANAGE_PY=$([ -f "$p/manage.py" ] && echo present || echo missing)"
echo "STAGING_GIT=$([ -d "$p/.git" ] && echo present || echo missing)"
echo "STAGING_ENV_FILE=$([ -f "$p/.env" ] && echo present || echo missing)"
echo "STAGING_PASSENGER_WSGI=$([ -f "$p/passenger_wsgi.py" ] && echo present || echo missing)"
if [ -d "$p/.git" ]; then
  git -C "$p" rev-parse --short HEAD 2>/dev/null || true
fi
for path in / /agriculture/ /agricultural-topics/agricultural-services/; do
  code="$(curl -sS -L -o /dev/null -w '%{http_code}' --max-time 12 "https://staging.zomorodmelal.ir$path" 2>/dev/null || echo network_error)"
  printf 'HTTP %s %s\n' "$path" "$code"
done
echo "NO_ENV_VALUES_OR_LOG_CONTENT_EXPOSED"
REMOTE
