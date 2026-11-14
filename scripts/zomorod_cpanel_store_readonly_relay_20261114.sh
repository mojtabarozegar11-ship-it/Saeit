#!/usr/bin/env bash
# Pinned, bounded READ-ONLY cPanel attestation. All temporary writes are runner-local.
set -euo pipefail
umask 077
test -n "$RUNNER_TEMP"
test -n "$VPS_KEY" && test -n "$HOST_KEY" || {
  echo "ZM_CPANEL_PROVENANCE_BLOCKED=missing_credentials" >&2
  exit 4
}
d="$(mktemp -d "$RUNNER_TEMP/zm-store-readonly.XXXXXX")"
trap 'rm -rf -- "$d"' EXIT
printf '%s' "$VPS_KEY" | python3 -c 'import sys;s=sys.stdin.read();print(s.replace(chr(13)+chr(10),chr(10)).replace(chr(13),"").replace(chr(92)+"n",chr(10)).rstrip()+chr(10),end="")' > "$d/vps.key"
printf '%s' "$HOST_KEY" | python3 -c 'import sys;s=sys.stdin.read();print(s.replace(chr(13)+chr(10),chr(10)).replace(chr(13),"").replace(chr(92)+"n",chr(10)).rstrip()+chr(10),end="")' > "$d/host.key"
chmod 600 "$d/vps.key" "$d/host.key"
ssh-keygen -y -P "" -f "$d/vps.key" >/dev/null
ssh-keygen -y -P "" -f "$d/host.key" >/dev/null
scan=""
for attempt in 1 2 3; do
  scan="$(ssh-keyscan -T 8 -t rsa 178.239.147.150 2>/dev/null || true)"
  test -n "$scan" && break
  sleep 2
done
test -n "$scan" || { echo "ZM_CPANEL_PROVENANCE_BLOCKED=vps_unreachable" >&2; exit 5; }
printf '%s\n' "$scan" > "$d/vps.known"
test "$(ssh-keygen -lf "$d/vps.known" -E sha256 | awk '{print $2}' | sort -u)" = "SHA256:AYdzF3K5uSwAXElE1w/dKo04iT2BbMGwHbRA2Cu4rrs" ||
 { echo "ZM_CPANEL_PROVENANCE_BLOCKED=vps_host_fingerprint_mismatch" >&2; exit 6; }
cat > "$d/config" <<EOF
Host saeit-vps
  HostName 178.239.147.150
  User githubops
  Port 22
  IdentityFile $d/vps.key
  UserKnownHostsFile $d/vps.known
Host saeit-cpanel
  HostName zohal.pws-dns.net
  User zomorod2
  Port 1396
  IdentityFile $d/host.key
  UserKnownHostsFile $d/host.known
  ProxyJump saeit-vps
Host *
  StrictHostKeyChecking yes
  IdentitiesOnly yes
  BatchMode yes
  ConnectTimeout 10
  ConnectionAttempts 1
  ForwardAgent no
  RequestTTY no
EOF
chmod 600 "$d/config"
scan=""
for attempt in 1 2 3; do
  scan="$(timeout 28s ssh -F "$d/config" saeit-vps 'timeout 15s ssh-keyscan -T 8 -p 1396 -t ed25519 zohal.pws-dns.net' 2>/dev/null || true)"
  test -n "$scan" && break
  sleep 2
done
test -n "$scan" || { echo "ZM_CPANEL_PROVENANCE_BLOCKED=cpanel_unreachable" >&2; exit 7; }
printf '%s\n' "$scan" > "$d/host.candidate"
test "$(ssh-keygen -lf "$d/host.candidate" -E sha256 | awk '{print $2}' | sort -u)" = "SHA256:7gQbDdrCVLFQRVdY6DAw8lF70jvlPfbJQslYn787E04" ||
 { echo "ZM_CPANEL_PROVENANCE_BLOCKED=cpanel_host_fingerprint_mismatch" >&2; exit 8; }
cp "$d/host.candidate" "$d/host.known"
echo "ZM_CPANEL_RELAY_PINNED=verified"
# Only remote process: python3 reading two bounded regular files. No remote writes.
timeout 45s ssh -T -F "$d/config" saeit-cpanel python3 - < scripts/zomorod_cpanel_store_provenance_readonly_20261114.py > "$d/remote-evidence.json"
python3 - "$d/remote-evidence.json" content/zomorod-v11/store_index.php <<'PY'
import hashlib,json,sys
from pathlib import Path
remote=json.loads(Path(sys.argv[1]).read_text(encoding="utf8"))
source=Path(sys.argv[2]).read_bytes()
remote["github_candidate_sha256"]=hashlib.sha256(source).hexdigest()
remote["active_php_matches_github_candidate"]=(remote["public_index_sha256"]==remote["github_candidate_sha256"])
assert remote["site_writes"]==0 and remote["payments"]==0
assert remote["forms_submitted"]==0 and remote["authentication_attempts"]==0
assert remote["private_content_disclosed"] is False
print("ZM_CPANEL_STORE_SOURCE_PROVENANCE="+json.dumps(remote,sort_keys=True),flush=True)
PY
