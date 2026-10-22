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
wrapper="$stage/f41_master_queue_with_finality.sh"
legacy="$stage/f41_master_queue_runner.sh"
test -x "$py"
test -f "$source" && test -f "$wrapper" && test -f "$legacy"
test -f "$target/factory_f41_shasta_finality.py"
test -f "$target/factory_f41_multi_product_builder.py"
test -f "$runner" && test ! -L "$runner"
test ! -L "$target"
test ! -L "$source"
test ! -L "$wrapper"
test ! -L "$target/factory_f41_auto_finality_scan.py"
# Do not replace an unknown existing master runner or unknown autoscan.
if ! cmp -s "$runner" "$legacy" && ! cmp -s "$runner" "$wrapper"; then
  echo F41_AUTOSCAN_MASTER_RUNNER_DRIFT_BLOCKED
  exit 1
fi
if test -f "$target/factory_f41_auto_finality_scan.py"; then
  cmp -s "$target/factory_f41_auto_finality_scan.py" "$source" || {
    echo F41_AUTOSCAN_EXISTING_MODULE_DRIFT_BLOCKED
    exit 1
  }
fi
bash -n "$wrapper"
bash -n "$legacy"
bash -n "$stage/install.sh"
"$py" -B -c 'import ast,sys;ast.parse(open(sys.argv[1],encoding="utf8").read())' "$source"
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
backup="$ops/backups/f41-runner-before-autoscan-$run_id"
test ! -L "$backup"
if ! test -e "$backup"; then
  install -m 600 "$runner" "$backup"
else
  cmp -s "$runner" "$backup" || cmp -s "$wrapper" "$runner"
fi
new_module="$target/.factory_f41_auto_finality_scan.$run_id.new"
install -m 600 "$source" "$new_module"
mv -f -- "$new_module" "$target/factory_f41_auto_finality_scan.py"
new_runner="$master/.run-f41-queue-autoscan.$run_id.new"
install -m 700 "$wrapper" "$new_runner"
mv -f -- "$new_runner" "$runner"
test "$(sha256sum "$source" | awk '{print $1}')" = "$(sha256sum "$target/factory_f41_auto_finality_scan.py" | awk '{print $1}')"
cmp -s "$runner" "$wrapper"
test "$(crontab -l | grep -Fc SAEIT_MASTER_F41_PRIVATE_QUEUE_V1)" -eq 1
# Verify the exact installed, authenticated master runner end-to-end now.
/usr/bin/timeout 120s /bin/bash "$runner"
echo F41_AUTOSCAN_AUTHENTIC_MASTER_CYCLE=PASS
echo F41_AUTOSCAN_INSTALLED_ON_VPS=PASS
echo F41_AUTOSCAN_MOJ1RO1_CRON_15MIN=ACTIVE
echo F41_AUTOSCAN_MAINNET_AND_SITE_WRITES=0
echo F41_AUTOSCAN_CUSTOMER_DELIVERY=false
