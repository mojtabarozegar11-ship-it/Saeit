#!/usr/bin/env bash
# Stage independently audited reviewer on existing factory VPS, then install.
set -euo pipefail
umask 077
test "${GITHUB_REF:-}" = "refs/heads/main"
test "${GITHUB_REPOSITORY:-}" = "mojtabarozegar11-ship-it/Saeit"
test -n "${VPS_KEY:-}"
[[ "${GITHUB_RUN_ID:-}" =~ ^[0-9]{5,18}$ ]]
[[ "${GITHUB_RUN_ATTEMPT:-}" =~ ^[0-9]{1,3}$ ]]
for f in scripts/factory_six_native_independent_rework.py deploy/install_factory_six_native_rework.sh; do
    test -s "$f" && test ! -L "$f"
done
work="$(mktemp -d)"
chmod 700 "$work"
trap 'rm -rf -- "$work"' EXIT
printf '%s' "$VPS_KEY" | python3 -c 'import sys;s=sys.stdin.buffer.read().decode("utf-8");s=s.replace("\r\n","\n").replace("\r","").replace("\\n","\n").rstrip()+"\n";sys.stdout.buffer.write(s.encode("utf-8"))' > "$work/key"
chmod 600 "$work/key"
ssh-keygen -y -P '' -f "$work/key" >/dev/null
ssh-keyscan -T 10 -t rsa 178.239.147.150 > "$work/known" 2>/dev/null
test "$(ssh-keygen -lf "$work/known" -E sha256 | awk '{print $2}' | sort -u)" = "SHA256:AYdzF3K5uSwAXElE1w/dKo04iT2BbMGwHbRA2Cu4rrs"
opts=(-i "$work/key" -o StrictHostKeyChecking=yes -o UserKnownHostsFile="$work/known"
    -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=15 -o ServerAliveInterval=10)
host="githubops@178.239.147.150"
source_run="$GITHUB_RUN_ID-$GITHUB_RUN_ATTEMPT"
stage="/home/githubops/factory-runtime/operations/.six-native-rework-$source_run"
ssh -T "${opts[@]}" "$host" "set -eu; umask 077; test \"\$(id -un)\" = githubops; test ! -e '$stage'; test -s \"/home/githubops/factory-runtime/private/autonomous-product-cycle/native-candidate-evidence/$source_run/verified-six-private-native.json\"; install -d -m 700 '$stage'"
for name in factory_six_native_independent_rework.py install_factory_six_native_rework.sh; do
    case "$name" in
      factory_six_native_independent_rework.py) from="scripts/$name";;
      *) from="deploy/$name";;
    esac
    scp -q "${opts[@]}" "$from" "$host:$stage/$name"
    wanted="$(sha256sum "$from" | cut -d' ' -f1)"
    actual="$(ssh -T "${opts[@]}" "$host" "sha256sum '$stage/$name' | cut -d' ' -f1")"
    test "$wanted" = "$actual"
done
timeout 300s ssh -T "${opts[@]}" "$host" "bash '$stage/install_factory_six_native_rework.sh' '$stage' '$source_run'"
echo SIX_NATIVE_SPECIALIST_QUEUE_INSTALLED_VPS=PASS
echo SIX_NATIVE_INDEPENDENT_TECHNICAL_REVIEW_CYCLE=15_MIN
echo SIX_NATIVE_QUALITY_1000_NOT_CERTIFIED=TRUE
