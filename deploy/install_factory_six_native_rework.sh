#!/usr/bin/env bash
# Private evidence-gated six native family review install. No website or sales writes.
set -euo pipefail
umask 077
test "$(id -un)" = "githubops" && test "$#" -eq 2
stage="$1"
run_id="$2"
[[ "$run_id" =~ ^[0-9]{5,18}-[0-9]{1,3}$ ]]
test -d "$stage" && test ! -L "$stage"
test -s "$stage/factory_six_native_independent_rework.py" && test ! -L "$stage/factory_six_native_independent_rework.py"
ops="$HOME/factory-runtime/operations"
private="$HOME/factory-runtime/private/autonomous-product-cycle"
target="$ops/six-native-rework"
py="$HOME/factory-runtime/.venv/bin/python"
marker="SAEIT_SIX_NATIVE_INDEPENDENT_REVIEW_V1"
test -x "$py" && test -d "$private" && test ! -L "$private"
test -s "$private/native-candidate-evidence/$run_id/verified-six-private-native.json"
test ! -L "$ops" && test ! -L "$target"
install -d -m 700 "$ops" "$target"
exec 9>"$ops/.six-native-rework-deploy.lock"
flock -w 90 9
backup="$target/.backup-$(date -u +%Y%m%dT%H%M%SZ)-$$"
install -d -m 700 "$backup"
if test -f "$target/factory_six_native_independent_rework.py"; then
    cp -p "$target/factory_six_native_independent_rework.py" "$backup/previous.py"
fi
crontab -l > "$backup/crontab-before"
cp -p "$stage/factory_six_native_independent_rework.py" "$target/.review-proposed.py"
test "$(sha256sum "$stage/factory_six_native_independent_rework.py" | cut -d' ' -f1)" = "$(sha256sum "$target/.review-proposed.py" | cut -d' ' -f1)"
"$py" -B -m py_compile "$target/.review-proposed.py"
rollback() {
    status=$?
    if test "$status" -ne 0; then
        if test -f "$backup/previous.py"; then
            cp -p "$backup/previous.py" "$target/factory_six_native_independent_rework.py"
        else
            rm -f "$target/factory_six_native_independent_rework.py"
        fi
        if crontab -l >/dev/null 2>&1; then
            crontab - < "$backup/crontab-before"
        fi
        echo SIX_NATIVE_REVIEW_INSTALL_ROLLED_BACK
    fi
    rm -f "$target/.review-proposed.py"
    return "$status"
}
trap rollback EXIT
install -m 600 "$target/.review-proposed.py" "$target/factory_six_native_independent_rework.py"
# Snapshot and re-evaluate all native receipts before adding any cron task.
"$py" -B "$target/factory_six_native_independent_rework.py" --factory-private "$private" --source-run "$run_id" | tee "$backup/acceptance.txt"
"$py" -B - "$private" "$run_id" <<'PY'
import json,sys
from pathlib import Path
root=Path(sys.argv[1]);run_id=sys.argv[2]
p=root/"quality-excellence"/"six-native-rework"/run_id/"review.json"
data=json.loads(p.read_text("utf8"))
assert data["schema"]=="saeit.factory.six-native-independent-technical-review.v1"
assert data["reviewed_families"]==6 and data["verified_native_candidate_files"]==56
assert len(data["families"])==6
assert data["completed_professional_quality_1000_certifications"]==0
assert data["independent_machine_review_performed"] is True
assert data["master_controller_connected_to_this_queue"] is False
assert data["commercial_release_authorized"] is False and data["website_changes"]==0
print("SIX_NATIVE_REWORK_REAL_PRIVATE_QA_QUEUE=6")
print("SIX_NATIVE_REWORK_SOURCE_DEFECTS="+str(data["source_rework_needed"]))
print("SIX_NATIVE_REWORK_SPECIALIST_APPROVAL=GATED")
PY
# Recheck the known previous native snapshot against its original SHA.
# This shows an actual F14 accessibility repair, not a declared improvement.
baseline="$private/native-candidate-evidence/39714521227-1/verified-six-private-native.json"
if test -s "$baseline" && test ! -L "$baseline"; then
    "$py" -B "$target/factory_six_native_independent_rework.py" --factory-private "$private" --source-run 39714521227-1 --expected-aggregate-sha256 bb1fa0e832ce6f840cff99f8aca1729cab1e4c6aa669635c10dd8b120e47b7ae > "$backup/baseline-review.txt"
    "$py" -B - "$private" "$run_id" <<'F14DELTA'
import json,sys
from pathlib import Path
base=Path(sys.argv[1])/"quality-excellence"/"six-native-rework"
prior=json.loads((base/"39714521227-1"/"F14.json").read_text())
current=json.loads((base/sys.argv[2]/"F14.json").read_text())
pre=set(prior["remediable_source_defects"])
post=set(current["remediable_source_defects"])
if not {"canvas_accessible_name_missing","score_live_region_missing"}.issubset(pre):
    raise RuntimeError("F14_BASELINE_MISSING_EXPECTED_DEFECTS")
if post.intersection(pre):
    raise RuntimeError("F14_ACCESSIBILITY_REWORK_NOT_FIXED")
if prior["artifact_sha256"]==current["artifact_sha256"]:
    raise RuntimeError("F14_SOURCE_VERSION_NOT_CHANGED")
print("F14_PROVEN_ACCESSIBILITY_DEFECTS_CLOSED="+str(len(pre-post)))
print("F14_NATIVE_ARTIFACT_VERSION_CHANGED=PASS")
F14DELTA
fi
if test "$(grep -Fc "$marker" "$backup/crontab-before")" -gt 1; then
    echo SIX_NATIVE_DUPLICATE_SCHEDULER
    exit 1
fi
if ! grep -Fq "$marker" "$backup/crontab-before"; then
    cp "$backup/crontab-before" "$backup/crontab-proposed"
    printf '7,22,37,52 * * * * /usr/bin/flock -n %s/.six-native-rework-periodic.lock /usr/bin/timeout 120s %s -B %s/factory_six_native_independent_rework.py --factory-private %s --latest >> %s/six-native-rework.log 2>&1 # %s\n' \
      "$ops" "$py" "$target" "$private" "$ops" "$marker" >> "$backup/crontab-proposed"
    # Atomic compare before changing the cron schedule.
    test "$(crontab -l | sha256sum | cut -d' ' -f1)" = "$(sha256sum "$backup/crontab-before" | cut -d' ' -f1)"
    crontab - < "$backup/crontab-proposed"
fi
test "$(crontab -l | grep -Fc "$marker")" -eq 1
trap - EXIT
rm -f "$target/.review-proposed.py"
echo SIX_NATIVE_INDEPENDENT_QA_15MIN_CRON=ACTIVE
echo SIX_NATIVE_REWORK_PRIVATE_SOURCE_RUN="$run_id"
echo SIX_NATIVE_REVIEW_PUBLIC_RELEASE=false
