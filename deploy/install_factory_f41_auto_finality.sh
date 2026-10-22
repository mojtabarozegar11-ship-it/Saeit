#!/usr/bin/env bash
# Safely attach Shasta-only finality scans to the existing F41 moj_1ro_1 cron.
set -euo pipefail
umask 077
stage="${1:?missing stage}"
run_id="${2:?missing run}"
[[ "$stage" =~ ^/home/githubops/factory-runtime/operations/\.f41-autoscan-stage-[0-9]+-[0-9]+$ ]]
[[ "$run_id" =~ ^[0-9]+$ ]]
[[ "$(id -un)" == githubops ]]
base=/home/githubops/factory-runtime
ops="$base/operations"
master="$ops/master-agent"
target="$ops/f41-multiproduct"
private="$base/private/autonomous-product-cycle"
py="$base/.venv/bin/python"
runner="$master/run-f41-queue.sh"
source="$stage/factory_f41_auto_finality_scan.py"
verified="$stage/factory_f41_shasta_finality.py"
builder="$stage/factory_f41_multi_product_builder.py"
wrapper="$stage/f41_master_queue_with_finality.sh"
legacy="$stage/f41_master_queue_runner.sh"
test -x "$py"
test -f "$source" && test -f "$verified" && test -f "$builder" && test -f "$wrapper" && test -f "$legacy"
test -f "$target/factory_f41_shasta_finality.py"
test -f "$target/factory_f41_multi_product_builder.py"
test -f "$runner" && test ! -L "$runner"
test ! -L "$target"
test ! -L "$source"
test ! -L "$verified"
test ! -L "$builder"
test ! -L "$wrapper"
test ! -L "$target/factory_f41_auto_finality_scan.py"
test ! -L "$target/factory_f41_shasta_finality.py"
test ! -L "$target/factory_f41_multi_product_builder.py"
# Reject unexpected on-VPS edits to any production module.
check_old_or_new() {
  local remote="$1" old="$2" staged="$3"
  local installed_sha stage_sha
  installed_sha="$(sha256sum "$remote" | awk '{print $1}')"
  stage_sha="$(sha256sum "$staged" | awk '{print $1}')"
  if [[ "$installed_sha" != "$old" && "$installed_sha" != "$stage_sha" ]]; then
    echo F41_TRC20_UPGRADE_UNEXPECTED_MODULE_DRIFT_BLOCKED
    exit 1
  fi
}
check_old_or_new "$target/factory_f41_multi_product_builder.py" "dd5962f0a400b1c947946b92ec12eb8bd8b7b9e9984094cffd76d26ef29c239c" "$builder"
check_old_or_new "$target/factory_f41_shasta_finality.py" "6a8021d5f9b886306f2cb974927ec0d585be3fc2d5d1048f6aa214fd79e25e97" "$verified"
check_old_or_new "$target/factory_f41_auto_finality_scan.py" "a3c2736a108ceaad3bc3b0085d088bda68155d41bf988529ed8be8954b34769b" "$source"
# Do not replace an unknown existing master runner.
if ! cmp -s "$runner" "$legacy" && ! cmp -s "$runner" "$wrapper"; then
  echo F41_AUTOSCAN_MASTER_RUNNER_DRIFT_BLOCKED
  exit 1
fi
bash -n "$wrapper"
bash -n "$legacy"
bash -n "$stage/install.sh"
"$py" -B -c 'import ast,sys;[ast.parse(open(p,encoding="utf8").read()) for p in sys.argv[1:]]' "$source" "$verified" "$builder"
test -d "$private/f41-multiproduct/orders"
test -d "$private/f41-multiproduct/outputs"
test -d "$target/assets"
install -d -m 700 "$private/f41-solidity-finality/automatic"
# Validate every existing master order; no RPC and no side effects here.
PYTHONPATH="$target" "$py" -B "$source" --dry-run
echo F41_AUTOSCAN_DRY_RUN=PASS
exec 9>"$master/master-cycle.lock"
flock -w 100 -x 9
if ! cmp -s "$runner" "$legacy" && ! cmp -s "$runner" "$wrapper"; then
  echo F41_AUTOSCAN_CONCURRENT_MASTER_DRIFT_BLOCKED
  exit 1
fi
check_old_or_new "$target/factory_f41_multi_product_builder.py" "dd5962f0a400b1c947946b92ec12eb8bd8b7b9e9984094cffd76d26ef29c239c" "$builder"
check_old_or_new "$target/factory_f41_shasta_finality.py" "6a8021d5f9b886306f2cb974927ec0d585be3fc2d5d1048f6aa214fd79e25e97" "$verified"
check_old_or_new "$target/factory_f41_auto_finality_scan.py" "a3c2736a108ceaad3bc3b0085d088bda68155d41bf988529ed8be8954b34769b" "$source"
backup="$ops/backups/f41-runner-before-autoscan-$run_id"
test ! -L "$backup"
if ! test -e "$backup"; then
  install -m 600 "$runner" "$backup"
else
  cmp -s "$runner" "$backup" || cmp -s "$wrapper" "$runner"
fi
# Stage and promote three compatible v2 modules while the authenticated F41 lock is held.
for module in factory_f41_multi_product_builder factory_f41_shasta_finality factory_f41_auto_finality_scan; do
  new_module="$target/.$module.$run_id.new"
  install -m 600 "$stage/$module.py" "$new_module"
  mv -f -- "$new_module" "$target/$module.py"
  test "$(sha256sum "$stage/$module.py" | awk '{print $1}')" = "$(sha256sum "$target/$module.py" | awk '{print $1}')"
done
new_runner="$master/.run-f41-queue-autoscan.$run_id.new"
install -m 700 "$wrapper" "$new_runner"
mv -f -- "$new_runner" "$runner"
test "$(sha256sum "$source" | awk '{print $1}')" = "$(sha256sum "$target/factory_f41_auto_finality_scan.py" | awk '{print $1}')"
cmp -s "$runner" "$wrapper"
test "$(crontab -l | grep -Fc SAEIT_MASTER_F41_PRIVATE_QUEUE_V1)" -eq 1
# Verify the exact installed, authenticated master runner end-to-end now.
/usr/bin/timeout 120s /bin/bash "$runner"
echo F41_TRC20_SHASTA_ALLOWLISTED_PROOF_CODE=INSTALLED
echo F41_TRC20_LIVE_ALLOWLIST_COUNT="$(printf '%s' "${F41_SHASTA_TRC20_ALLOWLIST:-}" | awk -F, 'END {print NR ? NF : 0}')"
echo F41_AUTOSCAN_AUTHENTIC_MASTER_CYCLE=PASS
echo F41_AUTOSCAN_INSTALLED_ON_VPS=PASS
echo F41_AUTOSCAN_MOJ1RO1_CRON_15MIN=ACTIVE
echo F41_AUTOSCAN_MAINNET_AND_SITE_WRITES=0
echo F41_AUTOSCAN_CUSTOMER_DELIVERY=false
