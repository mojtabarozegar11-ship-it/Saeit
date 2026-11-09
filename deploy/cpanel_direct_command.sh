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

work="$(mktemp -d "${RUNNER_TEMP}/saeit-cpanel-direct.XXXXXX")"
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

# Pin the previously authenticated public host key, without a network keyscan.
printf '%s\n' '178.239.147.150 ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQDJgT6PLND+DAA2JFptwG3gddczxCq19hWDragqn9oOZl1T6JpUTTptwKtAxALH6onbD/NIt1Kqg7QhJp5RHFek06mDPps5vO5okRf0q6uq7iGLJCd4zJHCIq1vmppLm1I1KmKvkmuG9VXxv07siYAUNlaZChhTXju9EzpmP6mAwkkiF76Q4/GCay545j7P4FmMezY7nqMAKvSgvU47/zA7w43WxtGjfmneAI0GBydwy22931IYkfjRr3dtDrfreJqhFQMdHDN7TOqlCFf0/F8Ri7VGOKLhwoZd1rTnK6MJcdSlNeXfNFOxaEw3Vt0MBSi4y9ahnjvRCsaUbDfUKbaGOhtepT/V/jrLsGOsrfgWaKoPaaq5TeP86FxH3oxB40QqHBUiIzPdvDqS3sirBLT0TsQ4/502IhymU/FX7dAMVyD+xYHGDKXeuqNH1wp+KJULvatTzOi41P28YDtZKsgRLKI7SY+AIYf+KCTTbYkt960bftKrSRmBWXl7XO/nzHU=' > "$work/vps.known"
chmod 600 "$work/vps.known"
test "$(ssh-keygen -lf "$work/vps.known" -E sha256 | awk '{print $2}' | sort -u)" = "SHA256:AYdzF3K5uSwAXElE1w/dKo04iT2BbMGwHbRA2Cu4rrs"

# Pin the previously authenticated cPanel SSH host key, independent of VPS reachability.
printf '%s\n' '[178.239.147.125]:1396 ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIE9vaKJLZ+5IhpcoTWOpsR9jauZVBqxOUpBHXS7Rh/Ia' > "$work/host.known"
chmod 600 "$work/host.known"
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
    timeout 60s ssh -T -F "$work/config" saeit-cpanel 'test "$(id -un)" = "zomorod2" && printf "CPANEL_SSH=READY\n"'
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
