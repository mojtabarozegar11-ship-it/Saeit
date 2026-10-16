#!/usr/bin/env bash
# Runs from an explicitly owner-gated GitHub issue; no keys are printed.
set -euo pipefail
umask 077
test -n "$VPS_KEY" && test -n "$HOST_KEY"
test -n "$GITHUB_RUN_ID"
d="$RUNNER_TEMP/personal-batch02-pinned-relay"
mkdir -p "$d"
finish() {
  rm -rf -- "$d"
}
trap finish EXIT
printf '%s\n' "$VPS_KEY" > "$d/vps.key"
printf '%s\n' "$HOST_KEY" > "$d/host.key"
python3 - "$d/host.key" <<'PYNORMALIZE'
import pathlib,sys
p=pathlib.Path(sys.argv[1])
s=p.read_text().replace("\r\n","\n").strip().replace("\\n","\n")
p.write_text(s+"\n")
PYNORMALIZE
chmod 600 "$d/vps.key" "$d/host.key"
ssh-keygen -y -P "" -f "$d/vps.key" >/dev/null
ssh-keygen -y -P "" -f "$d/host.key" >/dev/null
ssh-keyscan -T 10 -t rsa 178.239.147.150 > "$d/vps.known" 2>/dev/null
test "$(ssh-keygen -lf "$d/vps.known" -E sha256 | awk '{print $2}' | sort -u)" = "SHA256:AYdzF3K5uSwAXElE1w/dKo04iT2BbMGwHbRA2Cu4rrs"
cat > "$d/config" <<EOF
Host saeit-vps
  HostName 178.239.147.150
  User githubops
  IdentityFile $d/vps.key
  UserKnownHostsFile $d/vps.known
  StrictHostKeyChecking yes
Host saeit-host
  HostName zohal.pws-dns.net
  User zomorod2
  Port 1396
  IdentityFile $d/host.key
  UserKnownHostsFile $d/host.known
  ProxyJump saeit-vps
  StrictHostKeyChecking yes
Host *
  BatchMode yes
  IdentitiesOnly yes
  ForwardAgent no
  RequestTTY no
  ConnectTimeout 10
  ConnectionAttempts 1
EOF
timeout 30s ssh -F "$d/config" saeit-vps 'ssh-keyscan -T 8 -p 1396 -t ed25519 zohal.pws-dns.net' > "$d/host.known" 2>/dev/null
test "$(ssh-keygen -lf "$d/host.known" -E sha256 | awk '{print $2}' | sort -u)" = "SHA256:7gQbDdrCVLFQRVdY6DAw8lF70jvlPfbJQslYn787E04"
stage="/home/zomorod2/.personal-ai-faq-batch02-stage-$GITHUB_RUN_ID"
timeout 25s ssh -F "$d/config" saeit-host "test ! -e '$stage' && install -d -m 700 '$stage'"
timeout 70s scp -F "$d/config" scripts/mojtaba_personal_ai_questions_batch_02_publish.py "saeit-host:$stage/installer.py"
timeout 70s scp -F "$d/config" scripts/mojtaba_personal_public_faq_safe_publish.py "saeit-host:$stage/mojtaba_personal_public_faq_safe_publish.py"
timeout 70s scp -F "$d/config" content/mojtaba_personal_ai_questions_batch_02_20261016.json "saeit-host:$stage/approved.json"
timeout 70s scp -F "$d/config" scripts/mojtaba_personal_ai_faq_batch02_host_release.sh "saeit-host:$stage/host_release.sh"
timeout 1100s ssh -F "$d/config" saeit-host "bash '$stage/host_release.sh' '$GITHUB_RUN_ID'"
