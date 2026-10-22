#!/usr/bin/env bash
# Private F26 guard: secure SSH relay, unchanged website and existing ONNX files.
set -euo pipefail
umask 077
test "${GITHUB_REF:-}" = "refs/heads/main"
test "${GITHUB_REPOSITORY:-}" = "mojtabarozegar11-ship-it/Saeit"
test -n "${VPS_KEY:-}"
[[ "${GITHUB_RUN_ID:-}" =~ ^[0-9]{6,18}$ ]]
[[ "${GITHUB_RUN_ATTEMPT:-}" =~ ^[0-9]{1,3}$ ]]
[[ "${GITHUB_SHA:-}" =~ ^[0-9a-f]{40}$ ]]
test "$#" -eq 3
guard="$1"
samples="$2"
research_script="$3"
test -s "$guard" && test ! -L "$guard"
test -s "$samples" && test ! -L "$samples"
test -s "$research_script" && test ! -L "$research_script"
test -s deploy/factory_f26_research_guard_private_install.py
tmp="$(mktemp -d)"
chmod 700 "$tmp"
trap 'rm -rf -- "$tmp"' EXIT
printf '%s' "$VPS_KEY" | python3 -c 'import sys;s=sys.stdin.buffer.read().decode("utf-8");s=s.replace("\r\n","\n").replace("\r","").replace("\\n","\n").rstrip()+"\n";sys.stdout.buffer.write(s.encode("utf-8"))' > "$tmp/key"
chmod 600 "$tmp/key"
ssh-keygen -y -P '' -f "$tmp/key" >/dev/null
ssh-keyscan -T 10 -t rsa 178.239.147.150 > "$tmp/known" 2>/dev/null
test "$(ssh-keygen -lf "$tmp/known" -E sha256 | awk '{print $2}' | sort -u)" = "SHA256:AYdzF3K5uSwAXElE1w/dKo04iT2BbMGwHbRA2Cu4rrs"
opts=(-i "$tmp/key" -o StrictHostKeyChecking=yes -o UserKnownHostsFile="$tmp/known" -o BatchMode=yes -o IdentitiesOnly=yes -o ConnectTimeout=15 -o ServerAliveInterval=10)
host="githubops@178.239.147.150"
run="$GITHUB_RUN_ID-$GITHUB_RUN_ATTEMPT"
base="/home/githubops/factory-runtime/private/autonomous-product-cycle"
stage="$base/f26-real-data-research/.incoming-guard-$run"
python3 - "$guard" "$samples" "$research_script" "$tmp" <<'PY'
import hashlib,json,sys
from pathlib import Path
files={"guard-spec.json":sys.argv[1],
       "rice-samples.csv":sys.argv[2],
       "factory_f26_rice_research_guard.py":sys.argv[3]}
root=Path(sys.argv[4])
hashes={}
for name,path in files.items():
    p=Path(path)
    assert p.is_file() and not p.is_symlink() and 0<p.stat().st_size<1_000_000
    dest=root/name
    dest.write_bytes(p.read_bytes())
    hashes[name]=hashlib.sha256(p.read_bytes()).hexdigest()
(root/"hash-manifest.json").write_text(json.dumps(hashes,sort_keys=True)+"\n")
PY
ssh -T "${opts[@]}" "$host" "set -eu; umask 077; test \"\$(id -un)\" = githubops; test -d '$base/f26-real-data-research'; test ! -e '$stage'; install -d -m 700 '$stage'"
for name in guard-spec.json rice-samples.csv factory_f26_rice_research_guard.py hash-manifest.json; do
    scp -q "${opts[@]}" "$tmp/$name" "$host:$stage/$name"
    local_sha="$(sha256sum "$tmp/$name" | cut -d' ' -f1)"
    remote_sha="$(ssh -T "${opts[@]}" "$host" "sha256sum '$stage/$name' | cut -d' ' -f1")"
    test "$local_sha" = "$remote_sha"
done
file="deploy/factory_f26_research_guard_private_install.py"
scp -q "${opts[@]}" "$file" "$host:$stage/private-installer.py"
local_sha="$(sha256sum "$file" | cut -d' ' -f1)"
remote_sha="$(ssh -T "${opts[@]}" "$host" "sha256sum '$stage/private-installer.py' | cut -d' ' -f1")"
test "$local_sha" = "$remote_sha"
ssh -T "${opts[@]}" "$host" "timeout 180s python3 -B '$stage/private-installer.py' --factory-private '$base' --run-id '$run' --source-commit '$GITHUB_SHA' --sha-manifest '$stage/hash-manifest.json'"
echo F26_RESEARCH_GUARD_VERSIONED_PRIVATE_TRANSFER=PASS
echo F26_RESEARCH_GUARD_LIVE_SITE_MUTATIONS=0
