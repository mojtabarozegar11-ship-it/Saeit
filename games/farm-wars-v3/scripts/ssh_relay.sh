#!/usr/bin/env bash
set -euo pipefail
test -n "$VPS_KEY" && test -n "$HOST_KEY"
umask 077
d="$RUNNER_TEMP/farm-v4-ssh";install -d -m 700 "$d"
printf '%s' "$VPS_KEY" | python3 -c 'import sys;s=sys.stdin.read();print(s.replace(chr(13)+chr(10),chr(10)).replace(chr(13),"").replace(chr(92)+"n",chr(10)).rstrip()+chr(10),end="")' > "$d/vps.key"
printf '%s' "$HOST_KEY" | python3 -c 'import sys;s=sys.stdin.read();print(s.replace(chr(13)+chr(10),chr(10)).replace(chr(13),"").replace(chr(92)+"n",chr(10)).rstrip()+chr(10),end="")' > "$d/host.key"
chmod 600 "$d/"*
ssh-keygen -y -P "" -f "$d/vps.key" >/dev/null
ssh-keygen -y -P "" -f "$d/host.key" >/dev/null
# Pinned key scan is read-only; retry transient VPS MaxStartups resets safely.
for attempt in 1 2 3 4; do
  if ssh-keyscan -T 10 -t rsa 178.239.147.150 > "$d/vps.known" 2>/dev/null &&
     test "$(ssh-keygen -lf "$d/vps.known" -E sha256 | awk '{print $2}' | sort -u)" = "SHA256:AYdzF3K5uSwAXElE1w/dKo04iT2BbMGwHbRA2Cu4rrs"; then
    break
  fi
  if test "$attempt" = 4; then echo 'Verified VPS host key temporarily unreachable' >&2; exit 1; fi
  sleep $((attempt*3))
done
cat > "$d/config" <<EOF
Host vps
  HostName 178.239.147.150
  User githubops
  IdentityFile $d/vps.key
  UserKnownHostsFile $d/vps.known
Host host
  HostName zohal.pws-dns.net
  User zomorod2
  Port 1396
  IdentityFile $d/host.key
  UserKnownHostsFile $d/host.known
  ProxyJump vps
Host *
  StrictHostKeyChecking yes
  IdentitiesOnly yes
  BatchMode yes
  ConnectTimeout 12
  ConnectionAttempts 1
  ControlMaster auto
  ControlPath $d/control-%C
  ControlPersist 12m
  ServerAliveInterval 20
  ServerAliveCountMax 3
  ForwardAgent no
  RequestTTY no
EOF
chmod 600 "$d/config"
for attempt in 1 2 3 4; do
  if timeout 30s ssh -F "$d/config" vps 'ssh-keyscan -T 8 -p 1396 -t ed25519 zohal.pws-dns.net' > "$d/host.known" 2>/dev/null &&
     test "$(ssh-keygen -lf "$d/host.known" -E sha256 | awk '{print $2}' | sort -u)" = "SHA256:7gQbDdrCVLFQRVdY6DAw8lF70jvlPfbJQslYn787E04"; then
    break
  fi
  if test "$attempt" = 4; then echo 'Verified hosting key temporarily unreachable' >&2; exit 1; fi
  sleep $((attempt*3))
done
# Keep one authenticated, host-key-pinned connection open for all subsequent
# page/site actions. Prevents VPS SSH MaxStartups rate-limit on rapid workflows.
for i in 1 2 3 4; do
  if timeout 35s ssh -T -F "$d/config" vps true &&
     timeout 35s ssh -T -F "$d/config" host true; then
    echo RIVER_PULSE_PINNED_SSH_RELAY=PASS
    exit 0
  fi
  sleep $((i*4))
done
echo 'Cannot establish reliable persistent VPS->cPanel relay' >&2
exit 1
