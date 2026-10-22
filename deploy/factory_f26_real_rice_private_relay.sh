#!/usr/bin/env bash
# Keep real licensed F26 research model private; no production product promotion.
set -euo pipefail
umask 077
test "${GITHUB_REF:-}" = "refs/heads/main"
test "${GITHUB_REPOSITORY:-}" = "mojtabarozegar11-ship-it/Saeit"
[[ "${GITHUB_RUN_ID:-}" =~ ^[0-9]{5,18}$ ]]
[[ "${GITHUB_RUN_ATTEMPT:-}" =~ ^[0-9]{1,3}$ ]]
[[ "${GITHUB_SHA:-}" =~ ^[0-9a-f]{40}$ ]]
test -n "${VPS_KEY:-}"
test "$#" -eq 1
output="$1"
test -d "$output" && test ! -L "$output"
test -s deploy/factory_f26_real_rice_private_install.py
python3 -B scripts/factory_f26_real_rice_research_pilot.py --verify "$output"
work="$(mktemp -d)"
chmod 700 "$work"
trap 'rm -rf -- "$work"' EXIT
tar -cf "$work/f26-research.tar" -C "$output" \
    rice_cultivar_real_pilot.onnx model_card.json \
    ATTRIBUTION_AND_LIMITS.txt manifest.json
bundle_sha="$(sha256sum "$work/f26-research.tar" | cut -d' ' -f1)"
printf '%s' "$VPS_KEY" | python3 -c 'import sys;s=sys.stdin.buffer.read().decode("utf8");s=s.replace("\r\n","\n").replace("\r","").replace("\\n","\n").rstrip()+"\n";sys.stdout.buffer.write(s.encode("utf8"))' > "$work/key"
chmod 600 "$work/key"
ssh-keygen -y -P '' -f "$work/key" >/dev/null
ssh-keyscan -T 10 -t rsa 178.239.147.150 > "$work/known" 2>/dev/null
test "$(ssh-keygen -lf "$work/known" -E sha256 | awk '{print $2}' | sort -u)" = "SHA256:AYdzF3K5uSwAXElE1w/dKo04iT2BbMGwHbRA2Cu4rrs"
opts=(-i "$work/key" -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes
      -o UserKnownHostsFile="$work/known" -o BatchMode=yes -o ConnectTimeout=15)
host="githubops@178.239.147.150"
private="/home/githubops/factory-runtime/private/autonomous-product-cycle"
run="${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT}"
stage="$private/f26-real-data-research/.incoming-$run"
ssh -T "${opts[@]}" "$host" "set -eu; umask 077; test \"\$(id -un)\" = githubops; test -d '$private/native-candidate-evidence'; test ! -L '$private'; install -d -m 700 '$private/f26-real-data-research'; test ! -e '$stage'; install -d -m 700 '$stage'"
scp -q "${opts[@]}" "$work/f26-research.tar" "$host:$stage/f26-research.tar"
scp -q "${opts[@]}" deploy/factory_f26_real_rice_private_install.py "$host:$stage/install.py"
source_sha="$(sha256sum deploy/factory_f26_real_rice_private_install.py | cut -d' ' -f1)"
ssh -T "${opts[@]}" "$host" "set -eu; test \"\$(sha256sum '$stage/f26-research.tar' | cut -d' ' -f1)\" = '$bundle_sha'; test \"\$(sha256sum '$stage/install.py' | cut -d' ' -f1)\" = '$source_sha'; python3 '$stage/install.py' --factory-private '$private' --run-id '$run' --source-commit '$GITHUB_SHA' --bundle-sha256 '$bundle_sha'"
echo FACTORY_F26_RICE_REAL_DATA_PRIVATE_VPS_TRANSFER=PASS
echo FACTORY_F26_48_PREVIOUS_MODELS_UNCHANGED=true
echo FACTORY_F26_RICE_PUBLIC_RELEASE=false
