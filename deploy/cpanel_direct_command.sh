#!/usr/bin/env bash
set -euo pipefail

# Direct cPanel bridge. Read-only allowlist only.
# The runner reaches cPanel through the pinned VPS jump host.
operation="${1:-}"
case "$operation" in
  relay_preflight|cpanel_version|passenger_inventory|cpanel_preflight|django_check|django_migrations|zomorod_fields_audit_live|zomorod_fields_verify_stream|mpw_source_provenance) ;;
  *) echo "CPANEL_DIRECT_OPERATION_DENIED" >&2; exit 64 ;;
esac

: "${HOST_KEY:?HOST_KEY is required}"
if [[ "${FACTORY_VPS_RUNNER:-0}" != "1" ]]; then
  : "${VPS_KEY:?VPS_KEY is required}"
fi

work="${RUNNER_TEMP}/saeit-cpanel-direct"
install -d -m 700 "$work"
cleanup() { rm -rf -- "$work"; }
trap cleanup EXIT

# Strictly read-only: stream a pinned source guard over SSH stdin. Never stage on cPanel.
zomorod_fields_audit_stream() {
  local guard=scripts/zomorod_fields_guard_20261113.py
  local approved_blob=aeffb90f93e690bcc94d320dcee5d9ed9b4c2e32
  if [[ ! -f "$guard" || -L "$guard" || "$(git hash-object -- "$guard")" != "$approved_blob" ]]; then
    echo "ZOMOROD_AUDIT_SOURCE_NOT_PINNED" >&2
    return 65
  fi
  timeout 90s ssh -T -F "$work/config" saeit-cpanel \
    'for py in python3.13 python3.12 python3.11 python3.10 python3.9 python3.8 python3 /opt/alt/python313/bin/python3.13 /opt/alt/python312/bin/python3.12 /opt/alt/python311/bin/python3.11 /opt/alt/python310/bin/python3.10 /opt/alt/python39/bin/python3.9 /opt/alt/python38/bin/python3.8 /home/zomorod2/virtualenv/Saeit/3.11/bin/python /home/zomorod2/virtualenv/Saeit/3.10/bin/python; do if command -v "$py" >/dev/null 2>&1 && "$py" -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)" 2>/dev/null; then exec "$py" -B - audit-live; fi; done; echo CPANEL_COMPATIBLE_PYTHON_NOT_FOUND >&2; exit 70' \
    < "$guard"
}

zomorod_fields_verify_stream() {
  local guard=scripts/zomorod_fields_guard_20261113.py
  local sender=scripts/zomorod_fields_stream_sender_20261113.py
  if [[ -L "$guard" || -L "$sender" || ! -f "$guard" || ! -f "$sender" ]] ||
     [[ "$(git hash-object -- "$guard")" != "aeffb90f93e690bcc94d320dcee5d9ed9b4c2e32" ]] ||
     [[ "$(git hash-object -- "$sender")" != "5f8c360d343a40de6e4f0bb80369e628f4a48717" ]]; then
    echo "ZOMOROD_VERIFIER_SOURCE_NOT_PINNED" >&2
    return 65
  fi
  PYTHONDONTWRITEBYTECODE=1 python3 -B "$sender" "$work/config"
}

normalize_key() {
  local value="$1" destination="$2"
  printf '%s' "$value" | python3 -c 'import sys; s=sys.stdin.read(); s=s.replace("\r\n","\n").replace("\r","").replace("\\n","\n").rstrip()+"\n"; sys.stdout.write(s)' > "$destination"
  chmod 600 "$destination"
  ssh-keygen -y -P "" -f "$destination" >/dev/null
}
if [[ "${FACTORY_VPS_RUNNER:-0}" == "1" ]]; then
  normalize_key "$HOST_KEY" "$work/host.key"
  ssh-keyscan -T 10 -p 1396 -t ed25519 zohal.pws-dns.net > "$work/host.known" 2>/dev/null
  test "$(ssh-keygen -lf "$work/host.known" -E sha256 | awk '{print $2}' | sort -u)" = "SHA256:7gQbDdrCVLFQRVdY6DAw8lF70jvlPfbJQslYn787E04"
  cat > "$work/config" <<EOF
Host saeit-cpanel
  HostName zohal.pws-dns.net
  User zomorod2
  Port 1396
  IdentityFile $work/host.key
  UserKnownHostsFile $work/host.known
  StrictHostKeyChecking yes
  IdentitiesOnly yes
  BatchMode yes
  ConnectTimeout 15
  ServerAliveInterval 20
  ServerAliveCountMax 3
  ForwardAgent no
  RequestTTY no
EOF
  chmod 600 "$work/config"
  case "$operation" in
    relay_preflight)
      printf 'VPS_RELAY=LOCAL_FACTORY_VPS
'
      timeout 60s ssh -T -F "$work/config" saeit-cpanel 'printf "CPANEL_SSH=READY
"; id -un; hostname'
      ;;
    cpanel_version)
      timeout 60s ssh -T -F "$work/config" saeit-cpanel 'uapi --output=json Version get'
      ;;
    zomorod_fields_audit_live)
      zomorod_fields_audit_stream
      ;;
    zomorod_fields_verify_stream)
      zomorod_fields_verify_stream
      ;;
    passenger_inventory)
      timeout 60s ssh -T -F "$work/config" saeit-cpanel 'uapi --output=json PassengerApps list_applications' | python3 scripts/mojplaywin_cpanel_readonly_inventory.py
      ;;
    mpw_source_provenance)
    test -f scripts/mpw_onepass_cpanel_source_provenance_readonly_20261113.py
    test ! -L scripts/mpw_onepass_cpanel_source_provenance_readonly_20261113.py
    test "$(git hash-object -- scripts/mpw_onepass_cpanel_source_provenance_readonly_20261113.py)" = "dfefb70fb137b8c9daaa20b2713846745dc8ec78" || { echo "MPW_READONLY_SOURCE_NOT_PINNED" >&2; exit 65; }
    PYTHONDONTWRITEBYTECODE=1 timeout 90s ssh -T -F "$work/config" saeit-cpanel 'PYTHONDONTWRITEBYTECODE=1 python3 -B -' \
      < scripts/mpw_onepass_cpanel_source_provenance_readonly_20261113.py
    ;;
  cpanel_preflight)
      timeout 90s ssh -T -F "$work/config" saeit-cpanel 'set -e; root=/home/zomorod2/Saeit; test -d "$root"; test -f "$root/manage.py"; test -f "$root/passenger_wsgi.py"; printf "CPANEL_ROOT=%s\\n" "$root"; for f in manage.py passenger_wsgi.py requirements.txt; do if test -f "$root/$f"; then printf "PRESENT=%s\\n" "$f"; else printf "MISSING=%s\\n" "$f"; fi; done; printf "CPANEL_PYTHON_CANDIDATE="; for p in "$root/.venv/bin/python" "$root/venv/bin/python" /home/zomorod2/virtualenv/Saeit/3.11/bin/python; do if test -x "$p"; then printf "%s\\n" "$p"; break; fi; done'
      ;;
    django_check)
      timeout 90s ssh -T -F "$work/config" saeit-cpanel 'set -e; root=/home/zomorod2/Saeit; test -f "$root/manage.py"; python=""; for candidate in "$root/.venv/bin/python" "$root/venv/bin/python" /home/zomorod2/virtualenv/Saeit/3.11/bin/python /home/zomorod2/virtualenv/Saeit/3.10/bin/python /home/zomorod2/virtualenv/mojplaywin.com/3.11/bin/python; do if test -x "$candidate" && "$candidate" -c "import django" >/dev/null 2>&1; then python="$candidate"; break; fi; done; if test -z "$python"; then echo DJANGO_PYTHON_NOT_FOUND; exit 1; fi; printf "DJANGO_ROOT=%s\\n" "$root"; printf "DJANGO_PYTHON=%s\\n" "$python"; cd "$root"; "$python" manage.py check'
      ;;  esac
  exit 0
fi

normalize_key "$VPS_KEY" "$work/vps.key"
normalize_key "$HOST_KEY" "$work/host.key"

ssh-keyscan -T 10 -t rsa 178.239.147.150 > "$work/vps.known" 2>/dev/null
test "$(ssh-keygen -lf "$work/vps.known" -E sha256 | awk '{print $2}' | sort -u)" = "SHA256:AYdzF3K5uSwAXElE1w/dKo04iT2BbMGwHbRA2Cu4rrs"

ssh -T -i "$work/vps.key" -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile="$work/vps.known" -o BatchMode=yes githubops@178.239.147.150   'ssh-keyscan -T 10 -p 1396 -t ed25519 zohal.pws-dns.net' > "$work/host.known" 2>/dev/null
test "$(ssh-keygen -lf "$work/host.known" -E sha256 | awk '{print $2}' | sort -u)" = "SHA256:7gQbDdrCVLFQRVdY6DAw8lF70jvlPfbJQslYn787E04"

cat > "$work/config" <<EOF
Host saeit-vps
  HostName 178.239.147.150
  User githubops
  IdentityFile $work/vps.key
  UserKnownHostsFile $work/vps.known
Host saeit-cpanel
  HostName zohal.pws-dns.net
  User zomorod2
  Port 1396
  IdentityFile $work/host.key
  UserKnownHostsFile $work/host.known
  ProxyJump saeit-vps
Host *
  StrictHostKeyChecking yes
  IdentitiesOnly yes
  BatchMode yes
  ConnectTimeout 15
  ConnectionAttempts 1
  ServerAliveInterval 20
  ServerAliveCountMax 3
  ForwardAgent no
  RequestTTY no
EOF
chmod 600 "$work/config"

case "$operation" in
  relay_preflight)
    timeout 45s ssh -T -F "$work/config" saeit-vps 'printf "VPS_RELAY=READY\n"'
    timeout 60s ssh -T -F "$work/config" saeit-cpanel 'printf "CPANEL_SSH=READY\n"; id -un; hostname'
    ;;
  cpanel_version)
    timeout 60s ssh -T -F "$work/config" saeit-cpanel 'uapi --output=json Version get'
    ;;
  zomorod_fields_audit_live)
    zomorod_fields_audit_stream
    ;;
  zomorod_fields_verify_stream)
    zomorod_fields_verify_stream
    ;;
  passenger_inventory)
    timeout 60s ssh -T -F "$work/config" saeit-cpanel 'uapi --output=json PassengerApps list_applications' |
      python3 scripts/mojplaywin_cpanel_readonly_inventory.py
    ;;
  mpw_source_provenance)
    test -f scripts/mpw_onepass_cpanel_source_provenance_readonly_20261113.py
    test ! -L scripts/mpw_onepass_cpanel_source_provenance_readonly_20261113.py
    test "$(git hash-object -- scripts/mpw_onepass_cpanel_source_provenance_readonly_20261113.py)" = "dfefb70fb137b8c9daaa20b2713846745dc8ec78" || { echo "MPW_READONLY_SOURCE_NOT_PINNED" >&2; exit 65; }
    PYTHONDONTWRITEBYTECODE=1 timeout 90s ssh -T -F "$work/config" saeit-cpanel 'PYTHONDONTWRITEBYTECODE=1 python3 -B -' \
      < scripts/mpw_onepass_cpanel_source_provenance_readonly_20261113.py
    ;;
  cpanel_preflight)
    timeout 90s ssh -T -F "$work/config" saeit-cpanel 'set -e; if test -d /home/zomorod2/Saeit; then root=/home/zomorod2/Saeit; else root=/home/zomorodm/repositories/Saeit; fi; bash "$root/scripts/cpanel_preflight.sh" "$root"'
    ;;
  django_check)
    timeout 90s ssh -T -F "$work/config" saeit-cpanel 'set -e; if test -d /home/zomorod2/Saeit; then root=/home/zomorod2/Saeit; python=/home/zomorod2/virtualenv/Saeit/3.11/bin/python; else root=/home/zomorodm/repositories/Saeit; python=/home/zomorodm/virtualenv/repositories/Saeit/3.11/bin/python; fi; test -x "$python"; cd "$root"; "$python" manage.py check'
    ;;
  django_migrations)
    timeout 90s ssh -T -F "$work/config" saeit-cpanel 'set -e; if test -d /home/zomorod2/Saeit; then root=/home/zomorod2/Saeit; python=/home/zomorod2/virtualenv/Saeit/3.11/bin/python; else root=/home/zomorodm/repositories/Saeit; python=/home/zomorodm/virtualenv/repositories/Saeit/3.11/bin/python; fi; test -x "$python"; cd "$root"; "$python" manage.py showmigrations --plan'
    ;;
esac
