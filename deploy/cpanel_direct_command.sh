#!/usr/bin/env bash
set -euo pipefail

# Direct cPanel bridge. Read-only allowlist only.
# Prefer the pinned direct SSH host; retain the pinned VPS relay as fallback.
operation="${1:-}"
case "$operation" in
  relay_preflight|cpanel_version|passenger_inventory|cpanel_preflight|django_check|django_migrations) ;;
  *) echo "CPANEL_DIRECT_OPERATION_DENIED" >&2; exit 64 ;;
esac

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
normalize_key "$HOST_KEY" "$work/host.key"
if [ -n "${VPS_KEY:-}" ]; then
  normalize_key "$VPS_KEY" "$work/vps.key"
fi

# Build both authenticated paths. The direct cPanel connection does not
# depend on the VPS relay or on the hosting provider's account portal.
cat > "$work/config" <<EOF
Host saeit-vps
  HostName 178.239.147.150
  User githubops
  IdentityFile $work/vps.key
  UserKnownHostsFile $work/vps.known
Host saeit-cpanel-direct
  HostName zohal.pws-dns.net
  User zomorod2
  Port 1396
  IdentityFile $work/host.key
  UserKnownHostsFile $work/host.known
  ProxyJump none
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

route=""
cpanel_target=""
stage="verify_direct_cpanel_host_key"
# The direct path must pass the same independently pinned fingerprint.
# Never replace a fingerprint mismatch with an unverified trust-on-first-use key.
if ssh-keyscan -T 10 -p 1396 -t ed25519 zohal.pws-dns.net > "$work/host.known" 2>/dev/null && test -s "$work/host.known"; then
  direct_fingerprint="$(ssh-keygen -lf "$work/host.known" -E sha256 | awk '{print $2}' | sort -u)"
  if [ "$direct_fingerprint" != "SHA256:7gQbDdrCVLFQRVdY6DAw8lF70jvlPfbJQslYn787E04" ]; then
    echo "CPANEL_DIRECT_HOST_FINGERPRINT_MISMATCH" >&2
    exit 1
  fi
  stage="authenticate_direct_cpanel"
  if timeout 35s ssh -T -F "$work/config" saeit-cpanel-direct 'test "$(id -un)" = "zomorod2"' >/dev/null 2>&1; then
    route="direct"
    cpanel_target="saeit-cpanel-direct"
    echo "CPANEL_PINNED_DIRECT_SSH=AUTHENTICATED"
  else
    echo "CPANEL_PINNED_DIRECT_SSH=UNAVAILABLE"
  fi
else
  echo "CPANEL_DIRECT_SSH_PORT=UNREACHABLE"
fi

if [ -z "$route" ]; then
  stage="verify_vps_host_key"
  test -n "${VPS_KEY:-}" || { echo "VPS_RELAY_KEY_UNCONFIGURED" >&2; exit 1; }
  # Fall back to the previously verified relay. All host keys remain pinned.
  for attempt in 1 2 3; do
    if ssh-keyscan -T 10 -t rsa 178.239.147.150 > "$work/vps.known" 2>/dev/null && test -s "$work/vps.known"; then
      vps_fingerprint="$(ssh-keygen -lf "$work/vps.known" -E sha256 | awk '{print $2}' | sort -u)"
      if [ "$vps_fingerprint" != "SHA256:AYdzF3K5uSwAXElE1w/dKo04iT2BbMGwHbRA2Cu4rrs" ]; then
        echo "VPS_HOST_FINGERPRINT_MISMATCH" >&2
        exit 1
      fi
      break
    fi
    if [ "$attempt" -eq 3 ]; then
      echo "VPS_HOST_KEY_UNREACHABLE" >&2
      exit 1
    fi
    sleep "$((attempt*3))"
  done

  stage="verify_cpanel_host_key_via_vps"
  if ! timeout 45s ssh -T -i "$work/vps.key" -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile="$work/vps.known" -o BatchMode=yes -o ConnectTimeout=15 githubops@178.239.147.150 'ssh-keyscan -T 10 -p 1396 -t ed25519 zohal.pws-dns.net' > "$work/host.known" 2>/dev/null; then
    echo "CPANEL_RELAY_HOST_KEY_UNREACHABLE" >&2
    exit 1
  fi
  test -s "$work/host.known" || { echo "CPANEL_RELAY_HOST_KEY_EMPTY" >&2; exit 1; }
  test "$(ssh-keygen -lf "$work/host.known" -E sha256 | awk '{print $2}' | sort -u)" = "SHA256:7gQbDdrCVLFQRVdY6DAw8lF70jvlPfbJQslYn787E04" || { echo "CPANEL_RELAY_HOST_FINGERPRINT_MISMATCH" >&2; exit 1; }
  route="relay"
  cpanel_target="saeit-cpanel"
fi

echo "CPANEL_ROUTE=$route"
stage="execute_selected_readonly_operation"
case "$operation" in
  relay_preflight)
    if [ "$route" = "relay" ]; then
      timeout 45s ssh -T -F "$work/config" saeit-vps 'printf "VPS_RELAY=READY\n"'
    fi
    timeout 60s ssh -T -F "$work/config" "$cpanel_target" 'printf "CPANEL_SSH=READY\n"; id -un; hostname'
    ;;
  cpanel_version)
    timeout 60s ssh -T -F "$work/config" "$cpanel_target" 'uapi --output=json Version get'
    ;;
  passenger_inventory)
    timeout 60s ssh -T -F "$work/config" "$cpanel_target" 'uapi --output=json PassengerApps list_applications' |
      python3 scripts/mojplaywin_cpanel_readonly_inventory.py
    ;;
  cpanel_preflight)
    timeout 90s ssh -T -F "$work/config" "$cpanel_target" 'set -e; if test -d /home/zomorod2/Saeit; then root=/home/zomorod2/Saeit; else root=/home/zomorodm/repositories/Saeit; fi; bash "$root/scripts/cpanel_preflight.sh" "$root"'
    ;;
  django_check)
    timeout 90s ssh -T -F "$work/config" "$cpanel_target" 'set -e; if test -d /home/zomorod2/Saeit; then root=/home/zomorod2/Saeit; python=/home/zomorod2/virtualenv/Saeit/3.11/bin/python; else root=/home/zomorodm/repositories/Saeit; python=/home/zomorodm/virtualenv/repositories/Saeit/3.11/bin/python; fi; test -x "$python"; cd "$root"; "$python" manage.py check'
    ;;
  django_migrations)
    timeout 90s ssh -T -F "$work/config" "$cpanel_target" 'set -e; if test -d /home/zomorod2/Saeit; then root=/home/zomorod2/Saeit; python=/home/zomorod2/virtualenv/Saeit/3.11/bin/python; else root=/home/zomorodm/repositories/Saeit; python=/home/zomorodm/virtualenv/repositories/Saeit/3.11/bin/python; fi; test -x "$python"; cd "$root"; "$python" manage.py showmigrations --plan'
    ;;
esac
