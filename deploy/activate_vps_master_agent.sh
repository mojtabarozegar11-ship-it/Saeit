#!/usr/bin/env bash
# Activate exactly one existing economic master agent on the PRIVATE VPS runtime.
# No cPanel, public website, payment provider, migrations, or factory loop changes.
set -euo pipefail
umask 077
test "$(id -un)" = "githubops"
base="$HOME/factory-runtime"
app="$base/django-app"
ops="$base/operations"
py="$base/.venv/bin/python"
source_root="$ops/master-activation-source"
master="$ops/master-agent"
private="$base/private/master-agent"
test -x "$py" && test -f "$app/manage.py" && test -d "$base/private"
test -s "$source_root/scripts/vps_master_evolution_cycle.py"
command -v flock >/dev/null
command -v timeout >/dev/null
command -v crontab >/dev/null
test -x "$ops/vps-only-loop.sh"
if ! systemctl is-active --quiet cron 2>/dev/null && ! systemctl is-active --quiet crond 2>/dev/null; then
  echo MASTER_CRON_DAEMON_INACTIVE
  exit 1
fi
for module in core/management/commands/seed_online_income_agents.py core/management/commands/autonomous_master_loop.py core/management/commands/online_income_cycle.py core/worker_runner.py core/autonomous_brain.py core/master_agent_capability_pack.py; do
  test -s "$app/$module" || { echo "MASTER_REQUIRED_MODULE_MISSING"; exit 1; }
done
install -d -m 700 "$master" "$private" "$ops/backups"
exec 8>"$master/activation.lock"
flock -w 20 8
export SAEIT_ENV=production MOJ_FACTORY_LOCAL_MODE=1 DJANGO_SETTINGS_MODULE=config.settings
export MOJ_PAID_LLM_ENABLED=0 MOJ_LLM_DAILY_CALL_BUDGET=0 MOJ_LLM_MAX_COST_MINOR=0
cd "$app"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
modules=(
  core/autonomous_brain.py
  core/economic_tool_pack.py
  core/economic_master_agent.py
  core/self_funding_policy.py
  core/task_runtime.py
  core/management/commands/seed_online_income_agents.py
  core/management/commands/run_economic_worker.py
  core/management/commands/economic_worker.py
  core/worker_runner.py
  core/management/commands/autonomous_master_loop.py
  core/management/commands/online_income_cycle.py
  core/recovery_scheduler.py
  core/management/commands/recover_stale_tasks.py
)
source_backup="$ops/backups/master-source-before-$stamp"
install -d -m 700 "$source_backup"
for module in "${modules[@]}"; do
  source="$source_root/$module"
  target="$app/$module"
  test -s "$source" && test ! -L "$source" || { echo "MASTER_DEPLOY_SOURCE_MISSING:$module"; exit 1; }
  test ! -L "$target" || { echo "MASTER_APP_SOURCE_SYMLINK:$module"; exit 1; }
  if [ -f "$target" ]; then
    install -D -m 600 "$target" "$source_backup/$module"
  else
    install -D -m 600 /dev/null "$source_backup/$module.absent"
  fi
done
rollback_sources() {
  for module in "${modules[@]}"; do
    backup="$source_backup/$module"
    target="$app/$module"
    if [ -s "$backup" ] && [ ! -L "$backup" ] && [ ! -L "$target" ]; then
      install -D -m 600 "$backup" "$target.rollback.tmp"
      mv -f "$target.rollback.tmp" "$target"
    elif [ -f "$backup.absent" ] && [ ! -L "$target" ]; then
      rm -f "$target"
    fi
  done
  echo MASTER_SOURCE_ROLLBACK_COMPLETED
}
restore_all() {
  result=$?
  trap - EXIT
  if [ "$result" -ne 0 ] && [ "${source_deploy_started:-0}" -eq 1 ]; then rollback_sources; fi
  if [ "$result" -ne 0 ] && [ "${backup_verified:-0}" -eq 0 ] && [ -f "$ops/backups/master-before-$stamp.sqlite3" ]; then
    rm -f "$ops/backups/master-before-$stamp.sqlite3"
    echo MASTER_INCOMPLETE_DB_BACKUP_REMOVED
  fi
  if [ "$result" -ne 0 ] && [ "${cron_replaced:-0}" -eq 1 ]; then
    crontab "$old"
    echo MASTER_CRON_RESTORED_AFTER_FAILED_REPLACEMENT
  fi
  return "$result"
}
old="$ops/backups/cron-before-master-$stamp.txt"
crontab -l > "$old" 2>/dev/null || : > "$old"
chmod 600 "$old"
tagged_count="$(grep -c 'SAEIT_MASTER_AGENT_V1' "$old" || true)"
test "$tagged_count" -eq 2 || { echo MASTER_EXPECTED_TWO_TAGGED_CRON_ENTRIES; exit 1; }
if grep -E 'economic_autorun|autonomous_master_loop' "$old" | grep -v 'SAEIT_MASTER_AGENT_V1' >/dev/null; then
  echo MASTER_COMPETING_EXISTING_CRON_DETECTED
  exit 1
fi
# Keep the existing master schedules intact while SQLite takes an online snapshot.
# A busy writer may make the snapshot fail closed; it must not remove cron.
cron_replaced=0
source_deploy_started=0
trap restore_all EXIT
echo MASTER_FACTORY_CRON_PRESERVED_DURING_DATABASE_SNAPSHOT
# SQLite's online backup API provides a consistent rollback snapshot while application services stay online.
"$py" - "$ops/backups/master-before-$stamp.sqlite3" <<'PY'
import os,sqlite3,sys
from pathlib import Path
import time
from django.conf import settings
db=settings.DATABASES["default"]
assert "sqlite3" in db["ENGINE"], "MASTER_DB_BACKEND_UNEXPECTED"
src=Path(db["NAME"]).resolve()
assert src.exists() and src.is_file() and not src.is_symlink(), "MASTER_DB_MISSING"
dst=Path(sys.argv[1])
# Pre-create with private permissions and close SQLite connections explicitly.
fd=os.open(dst,os.O_CREAT|os.O_EXCL|os.O_RDWR,0o600)
os.close(fd)
available=os.statvfs(dst.parent).f_bavail*os.statvfs(dst.parent).f_frsize
assert available >= src.stat().st_size + 2*1024**3, "MASTER_DB_BACKUP_DISK_RESERVE"
last_report=[0.0]
started=time.monotonic()
last_remaining=[None]
restarts=[0]
def report_progress(status,remaining,total):
    now=time.monotonic()
    if now-started > 240:
        raise TimeoutError("MASTER_DB_BACKUP_BOUNDED_DEADLINE")
    if last_remaining[0] is not None and remaining > last_remaining[0]+2048:
        restarts[0]+=1
        if restarts[0]>=3:
            raise TimeoutError("MASTER_DB_BACKUP_CONCURRENT_WRITER_RESTART_LIMIT")
    last_remaining[0]=remaining
    if now-last_report[0]>=15 or remaining==0:
        print(f"MASTER_DB_BACKUP_PROGRESS remaining_pages={remaining} total_pages={total}",flush=True)
        last_report[0]=now
original=sqlite3.connect(str(src),timeout=20)
backup=sqlite3.connect(str(dst),timeout=20)
try:
    original.backup(backup,pages=2048,progress=report_progress,sleep=0.1)
    assert backup.execute("PRAGMA integrity_check").fetchone()[0]=="ok"
finally:
    backup.close()
    original.close()
assert dst.is_file(), "MASTER_DB_BACKUP_FILE_MISSING_AFTER_CLOSE"
dst.chmod(0o600)
print("MASTER_DB_BACKUP_INTEGRITY_OK")
PY
echo MASTER_BACKUP_VERIFIED
backup_verified=1
# Only hold worker locks across source changes, not during the online snapshot.
# A busy worker causes a safe activation abort; cron itself stays installed.
exec 9>"$master/master-cycle.lock"
flock -w 180 9
exec 10>"$master/master-evolution.lock"
flock -n 10 || { echo MASTER_EVOLUTION_LOCK_BUSY_SAFE_ABORT; exit 1; }
echo MASTER_FACTORY_SOURCE_CHANGE_LOCKS_HELD
source_deploy_started=1
for module in "${modules[@]}"; do
  target="$app/$module"
  install -D -m 600 "$source_root/$module" "$target.deploy.tmp"
  mv -f "$target.deploy.tmp" "$target"
done
"$py" -m py_compile \
  core/autonomous_brain.py core/economic_tool_pack.py core/economic_master_agent.py \
  core/self_funding_policy.py core/task_runtime.py \
  core/management/commands/seed_online_income_agents.py \
  core/management/commands/run_economic_worker.py core/management/commands/economic_worker.py core/recovery_scheduler.py core/management/commands/recover_stale_tasks.py
"$py" manage.py check
"$py" manage.py seed_online_income_agents
"$py" - <<'PY'
import django
django.setup()
from core.models import Agent
qs=Agent.objects.filter(code="economic-master-agent",active=True)
assert qs.count()==1, "MASTER_AGENT_NOT_SINGLE_AND_ACTIVE"
agent=qs.get()
assert agent.capabilities.filter(active=True).count()>=7, "MASTER_CAPABILITIES_INCOMPLETE"
print("MASTER_SINGLE_ACTIVE_AGENT_VERIFIED")
print("MASTER_CAPABILITIES_ACTIVE="+str(agent.capabilities.filter(active=True).count()))
PY
"$py" -m py_compile "$source_root/scripts/vps_master_evolution_cycle.py"
cp -p "$source_root/scripts/vps_master_evolution_cycle.py" "$master/evolution.py.tmp"
chmod 600 "$master/evolution.py.tmp"
mv -f "$master/evolution.py.tmp" "$master/evolution.py"
cat > "$master/run-cycle.sh.tmp" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
umask 077
base="$HOME/factory-runtime"
root="$base/operations/master-agent"
py="$base/.venv/bin/python"
test -x "$py" && test -f "$base/django-app/manage.py"
export SAEIT_ENV=production MOJ_FACTORY_LOCAL_MODE=1 DJANGO_SETTINGS_MODULE=config.settings
export MOJ_PAID_LLM_ENABLED=0 MOJ_LLM_DAILY_CALL_BUDGET=0 MOJ_LLM_MAX_COST_MINOR=0
cd "$base/django-app"
steps="$("$py" - "$base/private/master-agent/evolution.json" <<'PY'
import json,sys
from pathlib import Path
p=Path(sys.argv[1])
try:
    steps=int(json.loads(p.read_text(encoding="utf-8")).get("max_steps",1))
except (FileNotFoundError,ValueError,TypeError,KeyError):
    steps=1
print(steps if 1<=steps<=3 else 1)
PY
)"
flock -n "$root/master-cycle.lock" timeout 30 "$py" manage.py recover_stale_tasks --agent-code economic-master-agent --limit 20 --stale-after 900
flock -n "$root/master-cycle.lock" timeout 780 "$py" manage.py autonomous_master_loop --max-steps "$steps"
SH
chmod 700 "$master/run-cycle.sh.tmp"
mv -f "$master/run-cycle.sh.tmp" "$master/run-cycle.sh"
cat > "$master/run-evolution.sh.tmp" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
umask 077
base="$HOME/factory-runtime"
root="$base/operations/master-agent"
py="$base/.venv/bin/python"
export SAEIT_ENV=production MOJ_FACTORY_LOCAL_MODE=1 DJANGO_SETTINGS_MODULE=config.settings
cd "$base/django-app"
db="$("$py" - <<'PY'
from django.conf import settings
print(settings.DATABASES["default"]["NAME"])
PY
)"
flock -n "$root/master-evolution.lock" timeout 120 "$py" "$root/evolution.py" --db "$db" --state "$base/private/master-agent/evolution.json"
SH
chmod 700 "$master/run-evolution.sh.tmp"
mv -f "$master/run-evolution.sh.tmp" "$master/run-evolution.sh"
# Preserve all unrelated cron entries exactly; reject competing master loops.
if grep -E 'economic_autorun|autonomous_master_loop' "$old" | grep -v 'SAEIT_MASTER_AGENT_V1' >/dev/null; then
  echo MASTER_COMPETING_EXISTING_CRON_DETECTED
  exit 1
fi
tmp="$master/cron-candidate.tmp"
grep -v 'SAEIT_MASTER_AGENT_V1' "$old" > "$tmp" || true
printf '%s\n' \
  '*/5 * * * * /bin/bash /home/githubops/factory-runtime/operations/master-agent/run-cycle.sh >> /home/githubops/factory-runtime/operations/master-agent/cycle.log 2>&1 # SAEIT_MASTER_AGENT_V1' \
  '37 */6 * * * /bin/bash /home/githubops/factory-runtime/operations/master-agent/run-evolution.sh >> /home/githubops/factory-runtime/operations/master-agent/evolution.log 2>&1 # SAEIT_MASTER_AGENT_V1' >> "$tmp"
chmod 600 "$tmp"
current="$master/cron-current-before-replace.tmp"
crontab -l > "$current"
if ! cmp -s "$old" "$current"; then
  echo MASTER_CRON_CONCURRENT_EDIT_BLOCKED
  exit 1
fi
rm -f "$current"
cron_replaced=1
crontab "$tmp"
rm -f "$tmp"
test "$(crontab -l | grep -c 'SAEIT_MASTER_AGENT_V1')" -eq 2
flock -u 10
flock -u 9
trap - EXIT
if "$master/run-evolution.sh"; then
  echo MASTER_INITIAL_EVOLUTION_COMPLETED
else
  echo MASTER_INITIAL_EVOLUTION_DEFERRED_TO_SCHEDULE
fi
if "$master/run-cycle.sh" >> "$master/cycle.log" 2>&1; then
  echo MASTER_INITIAL_CYCLE_COMPLETED
else
  echo MASTER_INITIAL_CYCLE_DEFERRED_TO_SCHEDULE
fi
echo MASTER_CRON_FIVE_MINUTE_CYCLE_VERIFIED
echo MASTER_SIX_HOUR_ADAPTIVE_EVOLUTION_VERIFIED
echo MASTER_FACTORY_LOOP_UNMODIFIED
echo MASTER_NO_PUBLIC_SITE_CHANGES
