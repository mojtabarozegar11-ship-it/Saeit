#!/usr/bin/env bash
# Trusted main-only, manual factory VPS -> existing cPanel SSH; no deployment.
set -euo pipefail
umask 077
test "$GITHUB_REF" = "refs/heads/main" || { echo "ZM_FACTORY_ATTEST_BLOCKED=not_main" >&2; exit 65; }
test "$GITHUB_EVENT_NAME" = "workflow_dispatch" || { echo "ZM_FACTORY_ATTEST_BLOCKED=not_manual" >&2; exit 65; }
test -n "$RUNNER_TEMP" && test -n "$HOST_KEY" || { echo "ZM_FACTORY_ATTEST_BLOCKED=missing_context" >&2; exit 65; }
test -f scripts/zomorod_cpanel_store_provenance_readonly_20261114.py
test ! -L scripts/zomorod_cpanel_store_provenance_readonly_20261114.py
test -f content/zomorod-v11/store_index.php
d="$(mktemp -d "$RUNNER_TEMP/zm-factory-cpanel.XXXXXX")"
trap 'rm -rf -- "$d"' EXIT
printf '%s' "$HOST_KEY" | python3 -c 'import sys;s=sys.stdin.read();sys.stdout.write(s.replace("\r\n","\n").replace("\r","").replace("\\n","\n").rstrip()+"\n")' > "$d/cpanel.key"
chmod 600 "$d/cpanel.key"
ssh-keygen -y -P '' -f "$d/cpanel.key" >/dev/null
timeout 15s ssh-keyscan -T 8 -p 1396 -t ed25519 178.239.147.125 > "$d/cpanel.known" 2>/dev/null ||
 { echo "ZM_FACTORY_ATTEST_BLOCKED=cpanel_keyscan_failed" >&2; exit 66; }
test -s "$d/cpanel.known" || { echo "ZM_FACTORY_ATTEST_BLOCKED=no_cpanel_key" >&2; exit 66; }
fp="$(ssh-keygen -lf "$d/cpanel.known" -E sha256 | awk '{print $2}' | sort -u)"
test "$fp" = "SHA256:7gQbDdrCVLFQRVdY6DAw8lF70jvlPfbJQslYn787E04" ||
 { echo "ZM_FACTORY_ATTEST_BLOCKED=cpanel_fingerprint_mismatch" >&2; exit 67; }
timeout 60s ssh -T -i "$d/cpanel.key" -p 1396 \
 -o UserKnownHostsFile="$d/cpanel.known" -o StrictHostKeyChecking=yes \
 -o IdentitiesOnly=yes -o BatchMode=yes -o ForwardAgent=no \
 -o ConnectTimeout=12 -o ConnectionAttempts=1 \
 zomorod2@178.239.147.125 \
 'for py in /home/zomorod2/virtualenv/Saeit/3.11/bin/python python3; do if command -v "$py" >/dev/null 2>&1; then exec "$py" -B -; fi; done; exit 70' \
 < scripts/zomorod_cpanel_store_provenance_readonly_20261114.py > "$d/remote.json"
python3 - "$d/remote.json" content/zomorod-v11/store_index.php "$RUNNER_TEMP/zm-factory-store-source.jsonl" <<'PY'
import hashlib, json, sys
from pathlib import Path
remote=json.loads(Path(sys.argv[1]).read_text(encoding="utf8"))
assert remote["scope"]=="native_store_cpanel_readonly"
assert remote["site_writes"]==0 and remote["payments"]==0
assert remote["authentication_attempts"]==0 and remote["forms_submitted"]==0
assert remote["private_content_disclosed"] is False
assert remote["verified_public_http_serving_parity"] is False
candidate=hashlib.sha256(Path(sys.argv[2]).read_bytes()).hexdigest()
out={
 "scope":"factory_runner_direct_cpanel_readonly",
 "active_public_index_sha256":remote["public_index_sha256"],
 "candidate_public_index_sha256":candidate,
 "source_hashes_match":remote["public_index_sha256"]==candidate,
 "active_file_wrap_rule_present":remote["active_file_wrap_rule_present"],
 "active_file_grid_rule_present":remote["active_file_grid_rule_present"],
 "active_file_has_native_db_call":remote["active_file_has_native_db_call"],
 "private_module_read_but_not_disclosed":True,
 "verified_public_http_serving_parity":False,
 "site_writes":0, "payments":0
}
line="ZM_FACTORY_STORE_ATTESTATION="+json.dumps(out,sort_keys=True)
Path(sys.argv[3]).write_text(line+"\n",encoding="utf8")
print(line)
PY
