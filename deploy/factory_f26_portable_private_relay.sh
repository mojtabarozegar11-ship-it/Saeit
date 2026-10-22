#!/usr/bin/env bash
# Private only; install no Python packages or public site changes.
set -euo pipefail
umask 077
test "${GITHUB_REF:-}" = "refs/heads/main"
test "${GITHUB_REPOSITORY:-}" = "mojtabarozegar11-ship-it/Saeit"
[[ "${GITHUB_RUN_ID:-}" =~ ^[0-9]{6,18}$ ]]
[[ "${GITHUB_RUN_ATTEMPT:-}" =~ ^[0-9]{1,3}$ ]]
[[ "${GITHUB_SHA:-}" =~ ^[0-9a-f]{40}$ ]]
test -n "${VPS_KEY:-}"
test "$#" -eq 2
spec="$1"
csv="$2"
test -s "$spec" && test -s "$csv" && test ! -L "$spec" && test ! -L "$csv"
test -s scripts/factory_f26_real_rice_cli.py
test -s scripts/factory_f26_rice_onnx_portable.py
test -s deploy/factory_f26_portable_private_install.py
work="$(mktemp -d)"
chmod 700 "$work"
trap 'rm -rf -- "$work"' EXIT
printf '%s' "$VPS_KEY" | python3 -c 'import sys;s=sys.stdin.buffer.read().decode("utf8");s=s.replace("\r\n","\n").replace("\r","").replace("\\n","\n").rstrip()+"\n";sys.stdout.buffer.write(s.encode())' > "$work/key"
chmod 600 "$work/key"
ssh-keygen -y -P '' -f "$work/key" >/dev/null
ssh-keyscan -T 10 -t rsa 178.239.147.150 > "$work/known" 2>/dev/null
test "$(ssh-keygen -lf "$work/known" -E sha256 | awk '{print $2}' | sort -u)" = 'SHA256:AYdzF3K5uSwAXElE1w/dKo04iT2BbMGwHbRA2Cu4rrs'
opts=(-i "$work/key" -o StrictHostKeyChecking=yes -o UserKnownHostsFile="$work/known" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=15)
host="githubops@178.239.147.150"
run="$GITHUB_RUN_ID-$GITHUB_RUN_ATTEMPT"
private="/home/githubops/factory-runtime/private/autonomous-product-cycle"
stage="$private/f26-real-data-research/.incoming-portable-$run"
ssh -T "${opts[@]}" "$host" "set -eu; umask 077; test \"\$(id -un)\" = githubops; test -d '$private/f26-real-data-research/$run'; test ! -e '$stage'; install -d -m 700 '$stage'"
cp "$spec" "$work/portable-spec.json"
cp "$csv" "$work/rice-inference.csv"
cp scripts/factory_f26_real_rice_cli.py "$work/factory_f26_real_rice_cli.py"
cp scripts/factory_f26_rice_onnx_portable.py "$work/factory_f26_rice_onnx_portable.py"
cp deploy/factory_f26_portable_private_install.py "$work/install.py"
python3 - "$work" <<'PY'
import hashlib,json,sys
from pathlib import Path
root=Path(sys.argv[1])
names=("portable-spec.json","rice-inference.csv","factory_f26_real_rice_cli.py","factory_f26_rice_onnx_portable.py")
data={name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in names}
(root/"hash-manifest.json").write_text(json.dumps(data,sort_keys=True)+"\n")
PY
for file in portable-spec.json rice-inference.csv factory_f26_real_rice_cli.py factory_f26_rice_onnx_portable.py install.py hash-manifest.json; do
  scp -q "${opts[@]}" "$work/$file" "$host:$stage/$file"
  wanted="$(sha256sum "$work/$file" | cut -d' ' -f1)"
  got="$(ssh -T "${opts[@]}" "$host" "sha256sum '$stage/$file' | cut -d' ' -f1")"
  test "$wanted" = "$got"
done
ssh -T "${opts[@]}" "$host" "python3 -B '$stage/install.py' --factory-private '$private' --source-run '$run' --source-commit '$GITHUB_SHA' --hash-manifest '$stage/hash-manifest.json'"
echo F26_PORTABLE_PRIVATE_VPS_TRANSFER_AND_INFERENCE=PASS
echo F26_PORTABLE_MAIN_SITE_MUTATION=NONE
