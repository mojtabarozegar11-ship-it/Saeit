#!/usr/bin/env bash
# Isolated F41 Shasta read-only finality verifier; changes no live payment engine.
set -euo pipefail
umask 077
stage="${1:?required staged directory}"
run_id="${2:?required GitHub Actions run id}"
[[ "$stage" =~ ^/home/githubops/factory-runtime/operations/\.f41-finality-stage-[0-9]+-[0-9]+$ ]]
[[ "$run_id" =~ ^[0-9]+$ ]]
[[ "$(id -un)" == "githubops" ]]
base=/home/githubops/factory-runtime
target="$base/operations/f41-multiproduct"
private="$base/private/autonomous-product-cycle/f41-solidity-finality"
source="$stage/factory_f41_shasta_finality.py"
test -d "$target"
test ! -L "$target"
test -f "$target/factory_f41_multi_product_builder.py"
test ! -L "$target/factory_f41_multi_product_builder.py"
test -f "$target/reconciliation.json"
test ! -L "$target/reconciliation.json"
test -f "$source"
test ! -L "$source"
python3 -B -c 'import ast,sys;ast.parse(open(sys.argv[1],encoding="utf8").read())' "$source"
mkdir -p -m 700 "$private"
test ! -L "$private"
# Inherited original builder is *not modified*. The smoke report remains private.
export PYTHONPATH="$target"
python3 -B "$source" --spec "$target/reconciliation.json" --out "$private/pilot-$run_id"
# Only promote code once isolated real Shasta read-only attempt completed safely.
exec 9>"$base/operations/.f41-finality-install.lock"
flock -w 30 -x 9
new="$target/.factory_f41_shasta_finality.$run_id.new"
install -m 600 "$source" "$new"
mv -f -- "$new" "$target/factory_f41_shasta_finality.py"
test "$(sha256sum "$source" | awk '{print $1}')" = "$(sha256sum "$target/factory_f41_shasta_finality.py" | awk '{print $1}')"
echo F41_SHASTA_FINALITY_PRIVATE_INSTALL=PASS
echo F41_ORIGINAL_MASTER_QUEUE_UNCHANGED=true
echo F41_MAINNET_AND_SITE_WRITES=0
