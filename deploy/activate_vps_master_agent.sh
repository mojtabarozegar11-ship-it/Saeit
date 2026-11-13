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
for module in core/management/commands/seed_online_income_agents.py core/management/commands/autonomous_master_loop.py core/management/commands/online_income_cycle.py core/canonical_bot_identity.py core/worker_runner.py core/autonomous_brain.py core/master_agent_capability_pack.py; do
  test -s "$app/$module" || { echo "MASTER_REQUIRED_MODULE_MISSING"; exit 1; }
done
# A SQLite rollback snapshot needs at least the size of the live database on
# the backup filesystem. Refuse activation BEFORE changing cron if insufficient.
# No database rows are read, and this gate creates no files.
master_capacity_preflight() {
  SAEIT_ENV=production MOJ_FACTORY_LOCAL_MODE=1 DJANGO_SETTINGS_MODULE=config.settings \
    "$py" - "$ops" <<'PY'
import os
import sys
from pathlib import Path
from django.conf import settings

ops = Path(sys.argv[1])
database = settings.DATABASES["default"]
if "sqlite3" not in database["ENGINE"]:
    raise SystemExit("MASTER_CAPACITY_ABORT_UNEXPECTED_DB_ENGINE")
source = Path(database["NAME"])
if source.is_symlink() or not source.is_file():
    raise SystemExit("MASTER_CAPACITY_ABORT_UNSAFE_DB_PATH")
if ops.is_symlink() or not ops.is_dir():
    raise SystemExit("MASTER_CAPACITY_ABORT_UNSAFE_BACKUP_PARENT")
db_bytes = source.stat().st_size
fs = os.statvfs(ops)
available = fs.f_bavail * fs.f_frsize
total = fs.f_blocks * fs.f_frsize
# Keep room for live writes, SQLite backup journals, cron and rollback.
reserve = max(2 * 1024**3, (total * 5 + 99) // 100)
required = db_bytes + reserve
print("MASTER_CAPACITY_AVAILABLE_BYTES=" + str(available), flush=True)
print("MASTER_CAPACITY_REQUIRED_BYTES=" + str(required), flush=True)
if available < required:
    raise SystemExit("MASTER_CAPACITY_ABORT_INSUFFICIENT_FREE_SPACE")
print("MASTER_CAPACITY_PREFLIGHT_OK", flush=True)
PY
}
# Resolve config.settings relative to the live Django app before importing it.
# This read-only directory change precedes every backup or cron mutation.
cd "$app"
master_capacity_preflight
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
  core/isolated_upgrade_proof.py
  core/economic_master_agent.py
  core/self_funding_policy.py
  core/task_runtime.py
  core/management/commands/seed_online_income_agents.py
  core/management/commands/run_economic_worker.py
  core/management/commands/economic_worker.py
  core/worker_runner.py
  core/management/commands/autonomous_master_loop.py
  core/management/commands/online_income_cycle.py
  core/canonical_bot_identity.py
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
  if [ "$result" -ne 0 ]; then rollback_sources; fi
  if [ "$result" -ne 0 ] && [ "${backup_verified:-0}" -eq 0 ] && [ -f "$ops/backups/master-before-$stamp.sqlite3" ]; then
    rm -f "$ops/backups/master-before-$stamp.sqlite3"
    echo MASTER_INCOMPLETE_DB_BACKUP_REMOVED