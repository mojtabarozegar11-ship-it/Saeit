#!/usr/bin/env bash
set -euo pipefail

# Direct cPanel bridge. Read-only allowlist only.
# The runner reaches cPanel through the pinned VPS jump host.
operation="${1:-}"
case "$operation" in
  relay_preflight|cpanel_version|passenger_inventory|cpanel_preflight|django_check|django_migrations) ;;
  *) echo "CPANEL_DIRECT_OPERATION_DENIED" >&2; exit 64 ;;
esac

: "${VPS_KEY:?VPS_KEY is required}"
: "${HOST_KEY:?HOST_KEY is required}"

stage="prepare_key_material"

work="${RUNNER_TEMP}/saeit-cpanel-direct"
install -d -m 700 "$work"
cleanup() {
  local rc=$?
  if [ "$rc" -ne 0 ]; then
    printf 'CPANEL_DIRECT_FAILURE_STAGE=%s EXIT=%s\n' "$stage" "$rc" >&2
  fi
  rm -rf -- "$work"
}
trap cleanup EXIT

normalize_key() {
  local value="$1" destination="$2"
  printf '%s' "$value" | python3 -c 'import sys; s=sys.stdin.read(); s=s.replace("\r\n","\n").replace("\r","").replace("\\n","\n").rstrip()+"\n"; sys.stdout.write(s)' > "$destination"
  chmod 600 "$destination"
  ssh-keygen -y -P "" -f "$destination" >/dev/null
}
normalize_key "$VPS_KEY" "$work/vps.key"
normalize_key "$HOST_KEY" "$work/host.key"

stage="verify_vps_host_key"
# Retry bounded transient SSH MaxStartups or egress resets; never trust an unpinned key.
for attempt in 1 2 3; do
  if ssh-keyscan -T 10 -t rsa 178.239.147.150 > "$work/vps.known" 2>/dev/null &&
     test "$(ssh-keygen -lf "$work/vps.known" -E sha256 | awk '{print $2}' | sort -u)" = "SHA256:AYdzF3K5uSwAXElE1w/dKo04iT2BbMGwHbRA2Cu4rrs"; then
    break
  fi
  if test "$attempt" -eq 3; then
    echo "VPS_HOST_KEY_UNREACHABLE_OR_MISMATCHED" >&2
    exit 1
  fi
  sleep "$((attempt*3))"
done

stage="verify_cpanel_host_key_via_vps"
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

stage="execute_selected_readonly_operation"
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
