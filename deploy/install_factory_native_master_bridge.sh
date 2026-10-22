#!/usr/bin/env bash
# Private existing-master bridge, with preflight/backup and file/cron rollback.
set -euo pipefail
umask 077
test "$(id -un)" = githubops && test "$#" -eq 1
stage="$1"
base="$HOME/factory-runtime"
app="$base/django-app"
ops="$base/operations"
master="$ops/master-agent"
private="$base/private/autonomous-product-cycle"
py="$base/.venv/bin/python"
test -d "$stage" && test ! -L "$stage"
test -f "$app/manage.py" && test -x "$py"
test -x "$master/run-cycle.sh" && test -d "$private/quality-excellence/six-native-rework"
test "$(crontab -l | grep -c SAEIT_MASTER_AGENT_V1)" -eq 2
command -v flock >/dev/null
files=(
 core/factory_native_review_gateway.py
 core/factory_f41_gateway.py
 core/economic_tool_pack.py
 core/economic_master_agent.py
 core/management/commands/seed_online_income_agents.py
 core/management/commands/factory_native_enqueue.py
)
for name in "${files[@]}"; do
  test -s "$stage/$name" && test ! -L "$stage/$name"
  test -d "$(dirname "$app/$name")" && test ! -L "$app/$name"
done
test ! -L "$master/master-cycle.lock"
exec 9>"$master/master-cycle.lock"
flock -w 100 9
backup="$ops/backups/native-master-$(date -u +%Y%m%dT%H%M%SZ)-$$"
install -d -m 700 "$ops/backups" "$backup"
for name in "${files[@]}"; do
  install -d -m 700 "$backup/$(dirname "$name")"
  if test -f "$app/$name"; then cp -p "$app/$name" "$backup/$name"; fi
  "$py" -B -m py_compile "$stage/$name"
done
crontab -l > "$backup/cron-before"
test "$(grep -Fc SAEIT_MASTER_NATIVE_QA_BRIDGE_V1 "$backup/cron-before")" -le 1
cd "$app"
export SAEIT_ENV=production MOJ_FACTORY_LOCAL_MODE=1 DJANGO_SETTINGS_MODULE=config.settings
export MOJ_PAID_LLM_ENABLED=0 MOJ_LLM_DAILY_CALL_BUDGET=0 MOJ_LLM_MAX_COST_MINOR=0
"$py" - "$backup/sqlite-before.sqlite3" <<'PY'
import sqlite3,sys
from pathlib import Path
from django.conf import settings
db=settings.DATABASES["default"]
assert "sqlite3" in db["ENGINE"]
src=Path(db["NAME"])
assert src.is_file() and not src.is_symlink()
with sqlite3.connect(src.as_uri()+"?mode=ro",uri=True,timeout=25) as original:
    with sqlite3.connect(sys.argv[1]) as backup:
        original.backup(backup)
        assert backup.execute("PRAGMA integrity_check").fetchone()[0]=="ok"
Path(sys.argv[1]).chmod(0o600)
print("NATIVE_MASTER_SQLITE_ONLINE_BACKUP=PASS")
PY
rollback() {
  status=$?
  if test "$status" -ne 0; then
    for name in "${files[@]}"; do
      if test -f "$backup/$name"; then cp -p "$backup/$name" "$app/$name"
      else rm -f "$app/$name"; fi
    done
    if test -f "$backup/run-native-qa.sh"; then
      cp -p "$backup/run-native-qa.sh" "$master/run-native-qa.sh"
    else rm -f "$master/run-native-qa.sh"; fi
    crontab - < "$backup/cron-before" || :
    echo NATIVE_MASTER_SOURCE_CRON_ROLLED_BACK
  fi
}
trap rollback EXIT
for name in "${files[@]}"; do
  temp="$app/$name.native-$$"
  cp "$stage/$name" "$temp"
  if test -f "$backup/$name"; then chmod --reference="$backup/$name" "$temp"
  else chmod 644 "$temp"; fi
  test "$(sha256sum "$temp" | cut -d' ' -f1)" = "$(sha256sum "$stage/$name" | cut -d' ' -f1)"
  mv -f "$temp" "$app/$name"
done
"$py" manage.py check
"$py" manage.py seed_online_income_agents
"$py" manage.py factory_native_enqueue --dry-run
"$py" manage.py factory_native_enqueue --execute
"$py" - <<'PY'
import django
django.setup()
from pathlib import Path
from core.factory_native_review_gateway import latest_snapshot,snapshot
from core.models import Agent,AgentTask,AuditLog
root=Path.home()/"factory-runtime/private/autonomous-product-cycle"
run=latest_snapshot(root)
proof=snapshot(root,run)
master=Agent.objects.get(code="moj_1ro_1",active=True)
economic=Agent.objects.get(code="economic-master-agent",active=True)
assert not economic.capabilities.filter(code="factory_native_review",active=True).exists()
assert set(master.capabilities.filter(active=True).values_list("code",flat=True))=={"factory_native_review","factory_f41_private_build"}
assert master.capabilities.filter(code="factory_native_review",active=True,risk_level="low").count()==1
tasks=list(AgentTask.objects.filter(agent=master,action_type="factory_native_review",
           input_data__source_run=run).order_by("pk"))
assert len(tasks)==6
assert {x.input_data["family"] for x in tasks}=={"F12","F13","F14","F16","F17","F26"}
assert all(x.status=="completed" and x.execution_id and x.attempt_count>=1 and
           x.output_data.get("verified_effect") is True and
           x.output_data.get("quality_1000_certified") is False and
           x.output_data.get("commercial_release") is False for x in tasks)
count=AuditLog.objects.filter(action="tool_invocation_completed",
      target_type="AgentTask",target_id__in=[str(x.pk) for x in tasks]).count()
assert count>=6
assert proof["completed_professional_quality_1000_certifications"]==0
print("MOJ1RO1_NATIVE_REAL_MASTER_TASKS=6")
print("MOJ1RO1_NATIVE_REAL_MASTER_GATEWAY_AUDITS="+str(count))
print("MOJ1RO1_NATIVE_EXTERNAL_PROFESSIONAL_GATES=6")
print("MOJ1RO1_NATIVE_AGENT_IDENTITY="+master.code)
PY
if test -f "$master/run-native-qa.sh"; then cp -p "$master/run-native-qa.sh" "$backup/run-native-qa.sh"; fi
cat > "$master/run-native-qa.sh.proposed" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
umask 077
base="$HOME/factory-runtime"
export SAEIT_ENV=production MOJ_FACTORY_LOCAL_MODE=1 DJANGO_SETTINGS_MODULE=config.settings
export MOJ_PAID_LLM_ENABLED=0 MOJ_LLM_DAILY_CALL_BUDGET=0 MOJ_LLM_MAX_COST_MINOR=0
cd "$base/django-app"
"$base/.venv/bin/python" manage.py factory_native_enqueue --execute
SH
chmod 700 "$master/run-native-qa.sh.proposed"
mv -f "$master/run-native-qa.sh.proposed" "$master/run-native-qa.sh"
marker=SAEIT_MASTER_NATIVE_QA_BRIDGE_V1
if ! grep -Fq "$marker" "$backup/cron-before"; then
  cp "$backup/cron-before" "$backup/cron-proposed"
  printf '10,25,40,55 * * * * /usr/bin/flock -n %s/master-cycle.lock /usr/bin/timeout 140s /bin/bash %s/run-native-qa.sh >> %s/native-qa.log 2>&1 # %s\n' "$master" "$master" "$master" "$marker" >> "$backup/cron-proposed"
  test "$(crontab -l | sha256sum | cut -d' ' -f1)" = "$(sha256sum "$backup/cron-before" | cut -d' ' -f1)"
  crontab - < "$backup/cron-proposed"
fi
test "$(crontab -l | grep -Fc "$marker")" -eq 1
test "$(crontab -l | grep -c SAEIT_MASTER_AGENT_V1)" -eq 2
trap - EXIT
echo MOJ1RO1_NATIVE_REAL_FACTORY_AGENT_IDENTITY_CONNECTED=PASS
echo MOJ1RO1_NATIVE_15MIN_SCHEDULE=ACTIVE
echo MOJ1RO1_NATIVE_PUBLIC_RELEASES=0
echo MOJ1RO1_NATIVE_BACKUP="$backup"
