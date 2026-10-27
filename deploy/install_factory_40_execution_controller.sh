#!/usr/bin/env bash
# Safe complete 40-family queue installer on an already verified factory VPS.
# Runs one bounded specialist pilot per tick where a proven toolchain exists.
# Does NOT grant commerce release to a pilot or 50-stage technically built unit.
set -euo pipefail
umask 077
test "$(id -un)" = githubops && test "$(id -u)" -ne 0 && test "$#" -eq 1
source_dir="$1"
test -d "$source_dir" && test ! -L "$source_dir"
base="$HOME/factory-runtime"
ops="$base/operations"
private="$base/private/autonomous-product-cycle"
target="$ops/forty-execution"
registry="$ops/forty-family-master/forty_families.json"
toolchain="$ops/build-toolchain/toolchain-manifest.json"
py="$base/.venv/bin/python"
marker=SAEIT_FACTORY_FORTY_FAMILY_OPERATIONAL_DISPATCH_V1
test -x "$py" && test -d "$private" && test ! -L "$private"
test -s "$registry" && test ! -L "$registry"
test -s "$toolchain" && test ! -L "$toolchain"
test -s "$ops/fifty-family-bridge/factory_build50_family_bridge.py"
test -s "$private/production-warehouse/stock-register.json"
test "$(crontab -l | grep -c SAEIT_FACTORY_EVERY_MINUTE_V1)" -eq 1
test "$(crontab -l | grep -c SAEIT_FACTORY_LIFECYCLE_12_V1)" -eq 1
test "$(crontab -l | grep -c SAEIT_FACTORY_FORTY_FAMILY_MASTER_V1)" -eq 1
test "$(crontab -l | grep -c SAEIT_FACTORY_BUILD50_FORTY_FAMILY_BRIDGE_V1)" -eq 1
test ! -L "$target"
install -d -m 700 "$target" "$ops/backups"
exec 9>"$ops/.forty-execution-deploy.lock"
/usr/bin/flock -w 20 9 || { echo FORTY_EXEC_INSTALL_ALREADY_RUNNING;exit 1; }
stamp="$(date -u +%Y%m%dT%H%M%S)-$$"
backup="$ops/backups/forty-execution-$stamp"
install -d -m 700 "$backup"
crontab -l > "$backup/crontab-before.txt"
chmod 600 "$backup/crontab-before.txt"
for name in factory_six_specialist_executors.py factory_seven_missing_builders.py factory_40_execution_controller.py factory_40_family_master.py factory_build50_family_bridge.py factory_build_50.py factory_specialist_pilots.py factory_specialist_formats.py factory_build50_f31_planner.py factory_f31_independent_review.py factory_batch5_build.py factory_batch5_specs.py factory_batch5_review.py factory_product_planner.py factory_product_routes.py factory_build50_f18_webapps.py factory_f18_independent_review.py factory_capability_organizer.py factory_build50_f19_web_template.py factory_f19_independent_web_review.py factory_build50_f34_icon_kit.py factory_f34_independent_icon_review.py factory_build50_workbook.py factory_build50_creative_kits.py factory_creative_independent_review.py factory_build50_learning_4.py factory_learning_independent_review.py factory_build50_native_media.py factory_native_media_review.py factory_build50_five_publications.py factory_five_publication_review.py factory_build50_next4_media.py factory_next4_review.py factory_build50_three_media.py factory_three_independent_review.py factory_build50_f15_game_assets.py factory_f15_independent_review.py factory_build50_f24_prompts.py factory_f24_prompt_review.py factory_build50_f35_cad.py factory_f35_cad_independent_review.py;do
 test -s "$source_dir/$name" && test ! -L "$source_dir/$name"
 if test -f "$target/$name";then
  test ! -L "$target/$name"
  cp -p "$target/$name" "$backup/$name.previous"
 fi
 tmp="$(mktemp "$target/.staged-$name.XXXXXXXX")"
 install -m 600 "$source_dir/$name" "$tmp"
 mv -f "$tmp" "$target/$name"
done
"$py" -B -m py_compile "$target"/*.py
# Repair six previously blocked specialist producer routes using the real
# audited source/runtime builders, and verify their exact candidate ZIP bytes.
# Source pilots stay private and must NOT be counted as signed APK/EXE/ONNX.
"$py" -B "$target/factory_six_specialist_executors.py" --factory-private "$private" --all
"$py" -B - "$private" <<'SIXPROOF'
import json,sys
from pathlib import Path
p=Path(sys.argv[1])/"quality-excellence"/"six-agent-supervisor"/"last-execution.json"
d=json.loads(p.read_text(encoding="utf8"))
assert d["schema"]=="saeit.factory.six-specialist-executors.v1"
assert set(d["registered_workers"])=={"F12","F13","F14","F16","F17","F26"}
assert len(d["outcomes"])==6 and d["technical_candidates_rechecked"]==6
assert all(o["agent_executed"] and o["technical_candidate_hash_verified"] for o in d["outcomes"])
assert d["native_50_stage_executors_certified"]==0
assert d["independent_quality_1000_certified"]==0
assert not d["public_release_authorized"] and d["sites_modified"]==0
print("SIX_PRIVATE_SPECIALIST_AGENTS_REAL_ARTIFACTS_VERIFIED=6")
print("SIX_NATIVE_FINAL_RELEASES=0")
SIXPROOF
"$py" -B "$target/factory_build50_f18_webapps.py" --factory-private "$private"
# Five additional executable engineering families, each with independent BUILD50 proof.
"$py" -B "$target/factory_batch5_build.py" --factory-private "$private"
# One genuine dated F31 kit per week; repeated ticks verify instead of duplicating.
"$py" -B "$target/factory_build50_f31_planner.py" --factory-private "$private"
# Restore all three formerly disconnected catalog producers and verify exact receipts.
"$py" -B - "$target" "$private" <<'RESTORECATALOG'
import sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
import factory_product_planner as planner
root=Path(sys.argv[2]);proto=planner.load('factory_build_50')
for family in ('F19','F27','F34','F29','F30','F33','F06','F07','F10','F11','F36','F37','F39'):
 result=planner.execute(root,{'family_id':family})
 if not planner.proof(root,planner.CATALOG[family],family,proto):
  statefile=root/'build-50'/planner.CATALOG[family]/'state.json'
  defects=planner.read(statefile).get('defects',[]) if statefile.exists() else ['no_attempt_state']
  raise RuntimeError('CATALOG_RECOVERY_FAILED:'+family+':'+str(result)+':defects='+str(defects))
 print('CATALOG_ROUTE_AND_RECEIPTS_VERIFIED='+family)
RESTORECATALOG
# The restored catalog loop verifies real receipts for three new fixed-scope suites.
# Per-product planning covers all forty families and existing native WO requests.
"$py" -B "$target/factory_product_planner.py" --factory-private "$private" --registry "$registry"
"$py" -B - "$private" <<'PLANREQUEST'
import json,sys
from pathlib import Path
from datetime import date,timedelta
root=Path(sys.argv[1]);p=root/'product-planning/intake/qualification-next-week.json'
if p.is_symlink():raise RuntimeError('PLANNER_UNSAFE_QUALIFICATION_REQUEST')
if not p.exists():
 today=date.today();week=today-timedelta(days=today.weekday())+timedelta(days=7)
 data={'schema':'saeit.factory.product-request.v1','kind':'catalog','family_id':'F31','recipe':'weekly_planner','parameters':{'week':week.isoformat()}}
 with p.open('x',encoding='utf8') as stream:json.dump(data,stream,sort_keys=True)
p.chmod(0o600)
PLANREQUEST
"$py" -B "$target/factory_product_planner.py" --factory-private "$private" --registry "$registry" --dispatch --max-execute 40
# Admit only the fully proven package through the existing strict warehouse.
stock="$ops/production-warehouse/factory_production_warehouse.py"
test -s "$stock" && test ! -L "$stock"
stocked=0
for retry in 1 2 3 4 5;do
 "$py" -B "$stock" --factory-private "$private" --strict-build50
 if "$py" -B - "$private" <<'F31STOCK'
import json,sys
from pathlib import Path
from datetime import date,timedelta
root=Path(sys.argv[1]);today=date.today();week=today-timedelta(days=today.weekday())
product='fieldwork_planner_'+week.strftime('%Y%m%d')
manifest=json.loads((root/'digital-products'/product/'manufacturing_manifest.json').read_text())
stock=json.loads((root/'production-warehouse/stock-register.json').read_text())
assert stock['strict_build50_enabled'] is True
assert any(r['product_id']==product and r['family_id']=='F31' and r['artifact_sha256']==manifest['artifact_sha256'] for r in stock['records'])
print('F31_REAL_BUILD50_PRIVATE_STOCK=PASS')
for family,slug in [('F18','local_calculator_webapps'),('F20','validation_plugins'),('F21','developer_text_tools'),('F22','record_workflows'),('F25','synthetic_edge_fixtures'),('F28','engineering_calculators')]:
 product='fieldwork_'+slug
 manifest=json.loads((root/'digital-products'/product/'manufacturing_manifest.json').read_text())
 assert manifest['family_id']==family and manifest['qa_status']=='passed'
 assert any(r['product_id']==product and r['family_id']==family and r['artifact_sha256']==manifest['artifact_sha256'] for r in stock['records'])
print('BATCH5_REAL_BUILD50_PRIVATE_STOCK=PASS')
for family,product in [('F36','fieldwork_tileable_materials_48'),
 ('F37','fieldwork_animated_motion_48'),('F39','fieldwork_original_audio_cues_48')]:
 manifest=json.loads((root/'digital-products'/product/'manufacturing_manifest.json').read_text())
 assert manifest['family_id']==family and manifest['qa_status']=='passed'
 assert manifest['qa_evidence']=='unit_tests_passed' and len(manifest['files'])==97
 assert any(r['product_id']==product and r['family_id']==family and
            r['artifact_sha256']==manifest['artifact_sha256'] for r in stock['records'])
 print('NATIVE_MEDIA_STRICT_PRIVATE_STOCK='+family+':PASS')
F31STOCK
 then stocked=1;break;fi
 sleep 2
done
test "$stocked" -eq 1
# Reconcile copied support code, all family builder candidates and real tool consumers.
"$py" -B "$target/factory_capability_organizer.py" --factory-private "$private" --registry "$registry" --ops "$ops" --source-repo "$ops/multisite-deploy-source"
# The inspect run must never start a producer; verify exact registration first.
"$py" -B "$target/factory_40_execution_controller.py" --factory-private "$private" --registry "$registry" --module-dir "$target" --inspect-only
# Now run exactly one bounded, real, version-verified specialist pilot step.
"$py" -B "$target/factory_40_execution_controller.py" --factory-private "$private" --registry "$registry" --module-dir "$target" --toolchain-manifest "$toolchain"
"$py" -B - "$private" <<'PY'
import json,sys
from pathlib import Path
p=Path(sys.argv[1])/'production-family-management/forty-execution-dashboard.json'
d=json.loads(p.read_text('utf8'))
assert d['schema']=='saeit.factory.forty-family-operational-controller.v1'
assert d['registered_families']==40 and len(d['families'])==40
assert len({x['family_id'] for x in d['families']})==40
assert all(x['required_work_packages']==48 and not x['commercial_release_allowed'] for x in d['families'])
assert d['counts']['registered']==40
assert not d['commercial_release_enabled'] and not d['store_publication_enabled']
assert d['customer_orders_created']==0
print('FORTY_FAMILY_REAL_CONTROLLER_INITIAL_READBACK='+json.dumps(d['counts'],sort_keys=True))
print('FORTY_FAMILY_REAL_PILOT_TICK='+json.dumps(d['pilot_tick_result'],sort_keys=True))
PY
cat > "$target/periodic-dispatch.sh" <<SH
#!/usr/bin/env bash
set -euo pipefail
umask 077
exec 9>"$ops/.forty-execution-scheduler.lock"
/usr/bin/flock -n 9 || exit 0
exec >> "$ops/forty-execution.log" 2>&1
/usr/bin/timeout 90s "$py" -B "$target/factory_build50_f18_webapps.py" --factory-private "$private" || echo F18_PERIODIC_BUILD_REQUIRES_REWORK
/usr/bin/timeout 120s "$py" -B "$target/factory_batch5_build.py" --factory-private "$private" || echo BATCH5_PERIODIC_BUILD_REQUIRES_REWORK
/usr/bin/timeout 90s "$py" -B "$target/factory_build50_f31_planner.py" --factory-private "$private" || echo F31_PERIODIC_BUILD_REQUIRES_REWORK
/usr/bin/timeout 240s "$py" -B "$target/factory_product_planner.py" --factory-private "$private" --registry "$registry" --dispatch --max-execute 1 || echo PER_PRODUCT_PLANNER_REQUIRES_REVIEW
/usr/bin/timeout 45s "$py" -B "$target/factory_capability_organizer.py" --factory-private "$private" --registry "$registry" --ops "$ops" --source-repo "$ops/multisite-deploy-source" || echo CAPABILITY_ORGANIZER_REQUIRES_REVIEW
/usr/bin/timeout 135s "$py" -B "$target/factory_six_specialist_executors.py" --factory-private "$private" || echo SIX_SPECIALIST_AGENT_REWORK_PENDING
exec "$py" -B "$target/factory_40_execution_controller.py" --factory-private "$private" --registry "$registry" --module-dir "$target" --toolchain-manifest "$toolchain"
SH
chmod 700 "$target/periodic-dispatch.sh"
bash -n "$target/periodic-dispatch.sh"
entries="$(grep -c "$marker" "$backup/crontab-before.txt" || true)"
test "$entries" -le 1
if test "$entries" -eq 0;then
 cp "$backup/crontab-before.txt" "$backup/crontab-proposed.txt"
 printf '3-59/5 * * * * /bin/bash %s # %s\n' "$target/periodic-dispatch.sh" "$marker" >> "$backup/crontab-proposed.txt"
 test "$(crontab -l | sha256sum | awk '{print $1}')" = "$(sha256sum "$backup/crontab-before.txt" | awk '{print $1}')"
 crontab - < "$backup/crontab-proposed.txt"
else
 grep -Fq "$target/periodic-dispatch.sh" "$backup/crontab-before.txt"
fi
for job in "$marker" SAEIT_FACTORY_EVERY_MINUTE_V1 SAEIT_FACTORY_LIFECYCLE_12_V1 SAEIT_FACTORY_FORTY_FAMILY_MASTER_V1 SAEIT_FACTORY_BUILD50_FORTY_FAMILY_BRIDGE_V1;do
 test "$(crontab -l | grep -c "$job")" -eq 1
done
echo FORTY_FAMILY_PRIVATE_OPERATIONAL_QUEUE=ACTIVE
echo FORTY_FAMILY_PILOT_DISPATCH_EVERY_FIVE_MINUTES=ACTIVE
echo FORTY_FAMILY_OLD_PRODUCTION_AND_STORES=UNCHANGED
echo FORTY_FAMILY_AUTOMATIC_COMMERCIAL_APPROVAL=false
echo FORTY_FAMILY_BACKUP="$backup"
