#!/usr/bin/env bash
set -euo pipefail

# Pinned, read-only cPanel bridge. Prefer the VPS relay; use the already-
# fingerprint-verified direct cPanel SSH route when the relay is unreachable.
operation="${1:-}"
case "$operation" in
  relay_preflight|cpanel_version|passenger_inventory|cpanel_preflight|django_check|django_migrations) ;;
  *) echo "CPANEL_DIRECT_OPERATION_DENIED" >&2; exit 64 ;;
esac

: "${VPS_KEY:?VPS_KEY is required}"
: "${HOST_KEY:?HOST_KEY is required}"
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
normalize_key "$VPS_KEY" "$work/vps.key"
normalize_key "$HOST_KEY" "$work/host.key"

# Keys below are public host keys pinned and fingerprint-verified in the
# existing Zomorod v7 owner inventory workflow. Never trust a live keyscan.
printf '%s\n' '178.239.147.150 ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQDJgT6PLND+DAA2JFptwG3gddczxCq19hWDragqn9oOZl1T6JpUTTptwKtAxALH6onbD/NIt1Kqg7QhJp5RHFek06mDPps5vO5okRf0q6uq7iGLJCd4zJHCIq1vmppLm1I1KmKvkmuG9VXxv07siYAUNlaZChhTXju9EzpmP6mAwkkiF76Q4/GCay545j7P4FmMezY7nqMAKvSgvU47/zA7w43WxtGjfmneAI0GBydwy22931IYkfjRr3dtDrfreJqhFQMdHDN7TOqlCFf0/F8Ri7VGOKLhwoZd1rTnK6MJcdSlNeXfNFOxaEw3Vt0MBSi4y9ahnjvRCsaUbDfUKbaGOhtepT/V/jrLsGOsrfgWaKoPaaq5TeP86FxH3oxB40QqHBUiIzPdvDqS3sirBLT0TsQ4/502IhymU/FX7dAMVyD+xYHGDKXeuqNH1wp+KJULvatTzOi41P28YDtZKsgRLKI7SY+AIYf+KCTTbYkt960bftKrSRmBWXl7XO/nzHU=' > "$work/vps.known"
printf '%s\n' '[178.239.147.125]:1396 ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIE9vaKJLZ+5IhpcoTWOpsR9jauZVBqxOUpBHXS7Rh/Ia' > "$work/host.known"
vps_fp="$(ssh-keygen -lf "$work/vps.known" -E sha256 | awk '{print $2}')"
host_fp="$(ssh-keygen -lf "$work/host.known" -E sha256 | awk '{print $2}')"
test "$vps_fp" = 'SHA256:AYdzF3K5uSwAXElE1w/dKo04iT2BbMGwHbRA2Cu4rrs' || { echo "VPS_PIN_MISMATCH" >&2; exit 1; }
test "$host_fp" = 'SHA256:7gQbDdrCVLFQRVdY6DAw8lF70jvlPfbJQslYn787E04' || { echo "CPANEL_PIN_MISMATCH" >&2; exit 1; }
echo "PINNED_HOST_IDENTITIES=VERIFIED_OFFLINE"

cat > "$work/config" <<EOF
Host saeit-vps
  HostName 178.239.147.150
  User githubops
  Port 22
  IdentityFile $work/vps.key
  UserKnownHostsFile $work/vps.known
Host saeit-cpanel
  HostName 178.239.147.125
  User zomorod2
  Port 1396
  IdentityFile $work/host.key
  UserKnownHostsFile $work/host.known
  ProxyJump saeit-vps
Host saeit-cpanel-direct
  HostName 178.239.147.125
  User zomorod2
  Port 1396
  IdentityFile $work/host.key
  UserKnownHostsFile $work/host.known
  ProxyJump none
Host *
  StrictHostKeyChecking yes
  IdentitiesOnly yes
  BatchMode yes
  ConnectTimeout 12
  ConnectionAttempts 1
  ServerAliveInterval 15
  ServerAliveCountMax 3
  ForwardAgent no
  RequestTTY no
EOF
chmod 600 "$work/config"

if timeout 24s ssh -T -F "$work/config" saeit-cpanel 'test "$(id -un)" = zomorod2' >/dev/null 2>&1; then
  command_host=saeit-cpanel
  echo "CPANEL_ROUTE=PINNED_VPS_RELAY"
elif timeout 25s ssh -T -F "$work/config" saeit-cpanel-direct 'test "$(id -un)" = zomorod2' >/dev/null 2>&1; then
  command_host=saeit-cpanel-direct
  echo "CPANEL_ROUTE=PINNED_DIRECT_FALLBACK"
else
  echo "CPANEL_ROUTE=UNAVAILABLE_ON_BOTH_PINNED_PATHS" >&2
  exit 1
fi

case "$operation" in
  relay_preflight)
    if test "$command_host" = saeit-cpanel; then
      echo 'VPS_RELAY=READY'
    else
      echo 'VPS_RELAY=UNAVAILABLE'
    fi
    timeout 30s ssh -T -F "$work/config" "$command_host" 'printf "CPANEL_SSH=READY\n"; id -un; hostname'
    ;;
  cpanel_version)
    timeout 45s ssh -T -F "$work/config" "$command_host" 'uapi --output=json Version get'
    ;;
  passenger_inventory)
    timeout 45s ssh -T -F "$work/config" "$command_host" 'uapi --output=json PassengerApps list_applications' |
      python3 scripts/mojplaywin_cpanel_readonly_inventory.py
    ;;
  cpanel_preflight)
    timeout 90s ssh -T -F "$work/config" "$command_host" 'set -e; if test -d /home/zomorod2/Saeit; then root=/home/zomorod2/Saeit; else root=/home/zomorodm/repositories/Saeit; fi; bash "$root/scripts/cpanel_preflight.sh" "$root"'
    ;;
  django_check)
    timeout 90s ssh -T -F "$work/config" "$command_host" 'set -e; if test -d /home/zomorod2/Saeit; then root=/home/zomorod2/Saeit; python=/home/zomorod2/virtualenv/Saeit/3.10/bin/python; if test ! -x "$python"; then python=/home/zomorod2/virtualenv/Saeit/3.11/bin/python; fi; else root=/home/zomorodm/repositories/Saeit; python=/home/zomorodm/virtualenv/repositories/Saeit/3.11/bin/python; fi; test -x "$python"; printf "CPANEL_DJANGO_PYTHON_CANDIDATE=%s\n" "$python"; cd "$root"; "$python" manage.py check'
    ;;
  django_migrations)
    timeout 90s ssh -T -F "$work/config" "$command_host" 'set -e; if test -d /home/zomorod2/Saeit; then root=/home/zomorod2/Saeit; python=/home/zomorod2/virtualenv/Saeit/3.10/bin/python; if test ! -x "$python"; then python=/home/zomorod2/virtualenv/Saeit/3.11/bin/python; fi; else root=/home/zomorodm/repositories/Saeit; python=/home/zomorodm/virtualenv/repositories/Saeit/3.11/bin/python; fi; test -x "$python"; printf "CPANEL_DJANGO_PYTHON_CANDIDATE=%s\n" "$python"; cd "$root"; "$python" manage.py showmigrations --plan'
    ;;
esac
