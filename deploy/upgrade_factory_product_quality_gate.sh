#!/usr/bin/env bash
# Upgrade only the private VPS autonomous product runtime research QA modules.
# Never change factory DB, hourly schedules, public website, customer orders or payments.
set -Eeuo pipefail
umask 077
[[ "$(id -un)" == "githubops" && "$(id -u)" -ne 0 ]] || { echo QUALITY_UPGRADE_NONROOT_USER_REQUIRED; exit 2; }
base="$HOME/factory-runtime"
ops="$base/operations"
runtime="$ops/autonomous-product-runtime"
target="$runtime/scripts"
private="$base/private/autonomous-product-cycle"
recipes="$runtime/product_recipes"
python="$base/.venv/bin/python"
source_dir="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
db="$base/private/factory-fresh-isolated.sqlite3"
files=(factory_evidence_quality.py factory_autonomous_portfolio.py factory_vps_product_cycle.py)
test -d "$target" && test ! -L "$target"
test -f "$target/factory_first_product_pilot.py"
test -f "$target/factory_product_maker.py"
test -d "$recipes" && test -d "$private" && test -s "$db"
test -x "$python" && test -f "$ops/vps-only-loop.pid"
for f in "${files[@]}"; do
  test -f "$source_dir/scripts/$f" && test ! -L "$source_dir/scripts/$f"
done
read -r loop_pid < "$ops/vps-only-loop.pid"
[[ "$loop_pid" =~ ^[0-9]+$ ]] && kill -0 "$loop_pid"
echo FACTORY_MAIN_LOOP_ALIVE_BEFORE_QUALITY_SYNC
old_cron="$(crontab -l 2>/dev/null | sha256sum | cut -d' ' -f1)"
check="$ops/quality-gate-check-$$"
install -d -m 700 "$check/scripts" "$check/output"
test ! -L "$check"
install -m 600 "$target/factory_first_product_pilot.py" "$check/scripts/factory_first_product_pilot.py"
install -m 600 "$target/factory_product_maker.py" "$check/scripts/factory_product_maker.py"
for f in "${files[@]}"; do
  install -m 600 "$source_dir/scripts/$f" "$check/scripts/$f"
done
"$python" -B - "$check/scripts" <<'PY'
import ast,sys
from pathlib import Path
root=Path(sys.argv[1])
for name in ("factory_evidence_quality.py","factory_autonomous_portfolio.py","factory_vps_product_cycle.py"):
    ast.parse((root/name).read_text(encoding="utf-8"))
print("FACTORY_CANDIDATE_ALL_QUALITY_MODULES_PARSE")
PY
timeout 155 "$python" -B "$check/scripts/factory_vps_product_cycle.py" \
  --db "$db" --out "$check/output" --recipes "$recipes" \
  --max-products 3 --max-recipes 2
"$python" -B - "$check/output/production-state.json" <<'PY'
import json,sys
from pathlib import Path
d=json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert d["mode"]=="autonomous_supply_led"
assert d["technical_zip_checks_only"] is True
assert d["artifact_qa_passed"] is True
assert d["research_coverage_policy"]=="saeit.factory.research-readiness.v1"
assert d["commercial_quality_review_completed"] is False
assert d["publishable_product_count"] == 0
assert d["publication_locked_until_owner_approval"] is True
print("FACTORY_DISPOSABLE_PRODUCT_CYCLE_AND_RESEARCH_GATE_PASSED")
PY
# Lock both independent scheduling paths. A concurrent run must fail closed.
exec 9>"$ops/autonomous-product-cycle.lock"
flock -n 9 || { echo FACTORY_PRODUCT_CYCLE_BUSY_NO_MODIFICATIONS; exit 12; }
# Probe the secondary lock without holding it across run_cycle(), which takes
# that same lock internally. The primary wrapper lock protects Cron scheduling.
flock -n "$private/.production-cycle.lock" -c 'exit 0' ||
  { echo FACTORY_PRIVATE_CYCLE_BUSY_NO_MODIFICATIONS; exit 13; }
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup="$ops/backups/factory-quality-code-$stamp"
install -d -m 700 "$backup"
for f in "${files[@]}"; do
  if [[ -f "$target/$f" && ! -L "$target/$f" ]]; then
    cp -p -- "$target/$f" "$backup/$f"
    chmod 600 "$backup/$f"
  elif [[ -e "$target/$f" || -L "$target/$f" ]]; then
    echo FACTORY_QUALITY_MODULE_UNSAFE
    exit 14
  else
    touch "$backup/$f.absent"
    chmod 600 "$backup/$f.absent"
  fi
done
rollback_needed=true
rollback() {
  if [[ "$rollback_needed" == true ]]; then
    for f in "${files[@]}"; do
      if [[ -f "$backup/$f.absent" ]]; then
        rm -f -- "$target/$f"
      else
        cp -p -- "$backup/$f" "$target/$f"
      fi
    done
    echo FACTORY_QUALITY_DEPLOY_ROLLED_BACK
  fi
}
trap rollback EXIT
for f in "${files[@]}"; do
  tmp="$(mktemp "$target/.qa-replace.XXXXXXXX")"
  chmod 600 "$tmp"
  cp -- "$check/scripts/$f" "$tmp"
  mv -f -- "$tmp" "$target/$f"
done
echo FACTORY_PRIVATE_QUALITY_SCRIPTS_UPDATED
# The live production output is intentional, local private QA only, not a DB write.
timeout 155 "$python" -B "$target/factory_vps_product_cycle.py" \
  --db "$db" --out "$private" --recipes "$recipes" \
  --max-products 5 --max-recipes 2
"$python" -B - "$private/production-state.json" <<'PY'
import json,sys
from pathlib import Path
s=json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert s.get("research_coverage_policy")=="saeit.factory.research-readiness.v1"
assert s.get("technical_zip_checks_only") is True
assert s.get("artifact_qa_passed") is True
assert s.get("built_product_count")==2
assert s.get("publishable_product_count")==0
assert s.get("store_distribution_state")=="not_connected"
assert s.get("commercial_quality_review_completed") is False
assert s.get("publication_locked_until_owner_approval") is True
print("FACTORY_VPS_LIVE_PRODUCT_RESEARCH_GATE_VERIFIED")
print("FACTORY_VPS_RESEARCH_REVIEW_CANDIDATES="+str(s["research_review_candidate_count"]))
print("FACTORY_VPS_RESEARCH_DOSSIERS_UPDATED="+str(s["research_dossiers_updated"]))
print("FACTORY_VPS_QA_PACKAGES="+str(s["built_product_count"]))
print("FACTORY_VPS_PUBLICATION_ALLOWED=false")
PY
read -r after_pid < "$ops/vps-only-loop.pid"
[[ "$after_pid" =~ ^[0-9]+$ ]] && kill -0 "$after_pid"
test "$old_cron" = "$(crontab -l 2>/dev/null | sha256sum | cut -d' ' -f1)"
rollback_needed=false
trap - EXIT
echo FACTORY_MAIN_LOOP_ALIVE_AFTER_QUALITY_SYNC
echo FACTORY_CRONTAB_UNCHANGED_BY_QUALITY_SYNC
echo FACTORY_UPGRADE_CYCLE_READS_DB_ONLY
echo FACTORY_PRIVATE_QUALITY_GATE_DEPLOY_SUCCEEDED
