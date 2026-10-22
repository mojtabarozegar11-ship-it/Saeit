#!/usr/bin/env bash
# Private-only, hash-rechecked native candidate intake; NEVER a live deploy.
set -euo pipefail
umask 077
test "$#" -eq 2
family="$1"
case "$family" in F12|F13|F14|F16|F17|F26) ;; *) exit 2;; esac
test "${GITHUB_REF:-}" = "refs/heads/main" || {
  echo SIX_NATIVE_PRIVATE_RELAY=CI_ONLY; exit 0;
}
test "${GITHUB_REPOSITORY:-}" = "mojtabarozegar11-ship-it/Saeit"
test -n "${VPS_KEY:-}"
[[ "${GITHUB_RUN_ID:-}" =~ ^[0-9]+$ ]]
[[ "${GITHUB_RUN_ATTEMPT:-}" =~ ^[0-9]+$ ]]
src="$2"
if command -v cygpath >/dev/null 2>&1; then src="$(cygpath -u "$src")"; fi
test -d "$src" && test ! -L "$src"
test -s "$src/technical-native-candidate.zip"
test -s "$src/technical-native-receipt.json"
test -s scripts/factory_six_native_candidate_bundle.py
work="$(mktemp -d)"
chmod 700 "$work"
trap 'rm -rf -- "$work"' EXIT
printf '%s' "$VPS_KEY" | python -c 'import sys;s=sys.stdin.read();print(s.replace("\r\n","\n").replace("\r","").replace("\\n","\n").rstrip()+"\n",end="")' > "$work/key"
chmod 600 "$work/key"
ssh-keygen -y -P "" -f "$work/key" >/dev/null
ssh-keyscan -T 10 -t rsa 178.239.147.150 > "$work/known" 2>/dev/null
test "$(ssh-keygen -lf "$work/known" -E sha256 | awk '{print $2}' | sort -u)" = "SHA256:AYdzF3K5uSwAXElE1w/dKo04iT2BbMGwHbRA2Cu4rrs"
opts=(-i "$work/key" -o StrictHostKeyChecking=yes -o UserKnownHostsFile="$work/known"
  -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=15 -o ServerAliveInterval=10)
host="githubops@178.239.147.150"
base="/home/githubops/factory-runtime/private/autonomous-product-cycle/native-candidate-evidence"
stage="$base/$GITHUB_RUN_ID-$GITHUB_RUN_ATTEMPT/$family"
ssh -T "${opts[@]}" "$host" "set -eu; umask 077; test \"\$(id -un)\" = githubops; test -d '/home/githubops/factory-runtime/private/autonomous-product-cycle'; test ! -L '$base'; test ! -e '$stage'; mkdir -p -m 700 '$stage'; chmod 700 '$base' '$base/$GITHUB_RUN_ID-$GITHUB_RUN_ATTEMPT' '$stage'"
for file in technical-native-candidate.zip technical-native-receipt.json; do
  scp -q "${opts[@]}" "$src/$file" "$host:$stage/$file"
  expected="$(sha256sum "$src/$file" | awk '{print $1}')"
  actual="$(ssh -T "${opts[@]}" "$host" "sha256sum '$stage/$file' | cut -d' ' -f1")"
  test "$actual" = "$expected"
done
scp -q "${opts[@]}" scripts/factory_six_native_candidate_bundle.py "$host:$stage/factory_six_native_candidate_bundle.py"
expected="$(sha256sum scripts/factory_six_native_candidate_bundle.py | cut -d' ' -f1)"
actual="$(ssh -T "${opts[@]}" "$host" "sha256sum '$stage/factory_six_native_candidate_bundle.py' | cut -d' ' -f1")"
test "$actual" = "$expected"
ssh -T "${opts[@]}" "$host" "umask 077; chmod 600 '$stage'/*; python3 -B '$stage/factory_six_native_candidate_bundle.py' --verify --family '$family' --out '$stage'"
echo "SIX_NATIVE_PRIVATE_VPS_SHA_AND_MEMBER_READBACK=$family:PASS"
echo SIX_NATIVE_PUBLIC_RELEASE=false
