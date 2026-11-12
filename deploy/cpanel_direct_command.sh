#!/usr/bin/env bash
set -euo pipefail

# Direct cPanel bridge. Read-only allowlist only.
# The runner reaches cPanel through the pinned VPS jump host.
operation="${1:-}"
case "$operation" in
  relay_preflight|cpanel_version|passenger_inventory|cpanel_preflight|django_check|django_migrations) ;;
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

normalize_key() {
  local value="$1" destination="$2"
  printf '%s' "$value" | python3 -c 'import sys; s=sys.stdin.read(); s=s.replace("\r\n","\n").replace("\r","").replace("\\n","\n").rstrip()+"\n"; sys.stdout.write(s)' > "$destination"
  chmod 600 "$destination"
  ssh-keygen -y -P "" -f "$destination" >/dev/null
}
if [[ "${FACTORY_VPS_RUNNER:-0}" == "1" ]]; then
  normalize_key "$HOST_KEY" "$work/host.key"
  ssh-keyscan -T 10 -p 1396 -t ed25519 178.239.147.125 > "$work/host.known" 2>/dev/null
  test "$(ssh-keygen -lf "$work/host.known" -E sha256 | awk '{print $2}' | sort -u)" = "SHA256:7gQbDdrCVLFQRVdY6DAw8lF70jvlPfbJQslYn787E04"
  cat > "$work/config" <<EOF
Host saeit-cpanel
  HostName 178.239.147.125
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
    passenger_inventory)
      timeout 60s ssh -T -F "$work/config" saeit-cpanel 'uapi --output=json PassengerApps list_applications' | python3 scripts/mojplaywin_cpanel_readonly_inventory.py
      ;;
    cpanel_preflight)
      timeout 90s ssh -T -F "$work/config" saeit-cpanel 'set -e; if test -d /home/zomorod2/Saeit; then root=/home/zomorod2/Saeit; else root=/home/zomorodm/repositories/Saeit; fi; test -d "$root"; bash "$root/scripts/cpanel_preflight.sh" "$root"'
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

ssh -T -i "$work/vps.key" -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile="$work/vps.known" -o BatchMode=yes githubops@178.239.147.150   'ssh-keyscan -T 10 -p 1396 -t ed25519 178.239.147.125' > "$work/host.known" 2>/dev/null
test "$(ssh-keygen -lf "$work/host.known" -E sha256 | awk '{print $2}' | sort -u)" = "SHA256:7gQbDdrCVLFQRVdY6DAw8lF70jvlPfbJQslYn787E04"

cat > "$work/config" <<EOF
Host saeit-vps
  HostName 178.239.147.150
  User githubops
  IdentityFile $work/vps.key
  UserKnownHostsFile $work/vps.known
Host saeit-cpanel
  HostName 178.239.147.125
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
  passenger_inventory)
    timeout 60s ssh -T -F "$work/config" saeit-cpanel 'uapi --output=json PassengerApps list_applications' |
      python3 scripts/mojplaywin_cpanel_readonly_inventory.py
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
