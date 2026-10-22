#!/usr/bin/env bash
# Install real F41 AgentTask production bridge; keep sites, wallets and F01-F40 untouched.
set -euo pipefail
trap 'echo "F41_MASTER_INSTALL_FAILED_LINE=$LINENO"' ERR
umask 077
test "$#" -eq 1 && test "$(id -un)" = githubops
stage="$1"
base="$HOME/factory-runtime"
app="$base/django-app"
ops="$base/operations"
master="$ops/master-agent"
private="$base/private/autonomous-product-cycle/f41-multiproduct"
py="$base/.venv/bin/python"
test -d "$stage" && test ! -L "$stage"
test -x "$py" && test -f "$app/manage.py"
test -d "$private" && test -d "$ops/f41-multiproduct/assets"
test -f "$app/core/management/commands/factory_native_enqueue.py"
test -x "$master/run-native-qa.sh"
echo F41_MASTER_INITIAL_PATHS=PASS
test "$(crontab -l | grep -c SAEIT_MASTER_AGENT_V1)" -eq 2
command -v flock >/dev/null
echo F41_MASTER_CRON_AND_FLOCK=PASS
exec 9>"$master/master-cycle.lock"
flock -w 100 9
echo F41_MASTER_LOCK_ACQUIRED=PASS
changed=(
  core/economic_tool_pack.py
  core/management/commands/seed_online_income_agents.py
  core/management/commands/factory_native_enqueue.py
)
added=(
  core/factory_f41_gateway.py
  core/management/commands/factory_f41_enqueue.py
)
for f in "${changed[@]}"; do
  test -s "$stage/new/$f" && test -s "$stage/old/$f"
  test -f "$app/$f" && test ! -L "$app/$f"
  cmp -s "$app/$f" "$stage/old/$f" || {
    # A prior idempotent install may already have the new version.
    cmp -s "$app/$f" "$stage/new/$f" || {
      echo "F41_LIVE_DJANGO_SOURCE_DRIFT:$f"; exit 1;
    }
  }
done
for f in "${added[@]}"; do
  test -s "$stage/new/$f" && test ! -L "$app/$f"
  if test -e "$app/$f"; then
    cmp -s "$app/$f" "$stage/new/$f" || {
      echo "F41_UNKNOWN_EXISTING_BRIDGE:$f"; exit 1;
    }
  fi
done
echo F41_MASTER_LIVE_SOURCE_PREFLIGHT=PASS
for f in "${changed[@]}" "${added[@]}"; do
  "$py" -B -m py_compile "$stage/new/$f"
done
backup="$ops/backups/f41-master-$(date -u +%Y%m%dT%H%M%SZ)-$$"
install -d -m 700 "$ops/backups" "$backup"
for f in "${changed[@]}" "${added[@]}"; do
  install -d -m 700 "$backup/$(dirname "$f")"
  if test -f "$app/$f"; then cp -p "$app/$f" "$backup/$f"; fi
done
crontab -l > "$backup/cron-before"
test "$(grep -Fc SAEIT_MASTER_F41_PRIVATE_QUEUE_V1 "$backup/cron-before")" -le 1
for kind in vesting reconciliation provenance nft_metadata; do
  test -s "$ops/f41-multiproduct/samples/$kind.json"
done
install -d -m 700 "$private/orders" "$private/outputs"
for kind in vesting reconciliation provenance nft_metadata; do
  key="${kind//_/-}"
  target="$private/orders/F41-pilot-$key.json"
  test ! -L "$target"
  if test -e "$target"; then
    cmp -s "$target" "$ops/f41-multiproduct/samples/$kind.json" || {
      echo "F41_EXISTING_QUEUE_ID_COLLISION:$kind"; exit 1;
    }
  else
    install -m 600 "$ops/f41-multiproduct/samples/$kind.json" "$target"
  fi
done
cd "$app"
export SAEIT_ENV=production MOJ_FACTORY_LOCAL_MODE=1 DJANGO_SETTINGS_MODULE=config.settings
export MOJ_PAID_LLM_ENABLED=0 MOJ_LLM_DAILY_CALL_BUDGET=0 MOJ_LLM_MAX_COST_MINOR=0
"$py" - "$backup/sqlite-before.sqlite3" <<'PY'
import sqlite3,sys
from pathlib import Path
from django.conf import settings
db=settings.DATABASES["default"]
assert "sqlite3" in db["ENGINE"]
source=Path(db["NAME"])
assert source.is_file() and not source.is_symlink()
with sqlite3.connect(source.as_uri()+"?mode=ro",uri=True,timeout=25) as original:
    with sqlite3.connect(sys.argv[1]) as dest:
        original.backup(dest)
        assert dest.execute("PRAGMA integrity_check").fetchone()[0]=="ok"
Path(sys.argv[1]).chmod(0o600)
print("F41_MASTER_SQLITE_BACKUP=PASS")
PY
rollback_preseed() {
  status=$?
  if test "$status" -ne 0; then
    for f in "${changed[@]}" "${added[@]}"; do
      if test -f "$backup/$f"; then
        cp -p "$backup/$f" "$app/$f"
      else
        rm -f -- "$app/$f"
      fi
    done
    echo F41_MASTER_PREFLIGHT_SOURCE_RESTORED
  fi
}
trap rollback_preseed EXIT
for f in "${changed[@]}" "${added[@]}"; do
  install -m 600 "$stage/new/$f" "$app/$f.f41-$$"
  mv -f -- "$app/$f.f41-$$" "$app/$f"
done
"$py" manage.py check
"$py" manage.py factory_f41_enqueue --dry-run
trap - EXIT
"$py" manage.py seed_online_income_agents
# Existing six-family runtime must remain valid after expanding allowlist.
"$py" manage.py factory_native_enqueue --dry-run
"$py" manage.py factory_f41_enqueue --execute
"$py" -B - <<'PY'
import django
django.setup()
from core.models import Agent, AgentTask, AuditLog
agent=Agent.objects.get(code="moj_1ro_1",active=True)
assert set(agent.capabilities.filter(active=True).values_list("code",flat=True))=={
    "factory_native_review","factory_f41_private_build"}
tasks=list(AgentTask.objects.filter(agent=agent,action_type="factory_f41_private_build",
    input_data__order_id__startswith="F41-pilot-"))
assert len(tasks)==4 and {t.output_data["kind"] for t in tasks}=={
    "vesting","reconciliation","provenance","nft_metadata"}
assert all(t.status=="completed" and t.execution_id and
    t.output_data.get("verified_effect") is True and
    t.output_data.get("quality_1000_certified") is False and
    t.output_data.get("commercial_release") is False for t in tasks)
audits=AuditLog.objects.filter(action="tool_invocation_completed",
    target_type="AgentTask",target_id__in=[str(t.pk) for t in tasks]).count()
assert audits>=4
print("F41_MOJ1RO1_AUTHENTIC_TASKS=4")
print("F41_MOJ1RO1_AUDIT_LOGS="+str(audits))
PY
# Independent recurring queue scanner; no speculative orders are auto-minted.
runner="$master/run-f41-queue.sh"
test ! -L "$runner"
install -m 700 "$stage/runner.sh" "$runner.new-$$"
mv -f -- "$runner.new-$$" "$runner"
marker=SAEIT_MASTER_F41_PRIVATE_QUEUE_V1
if ! grep -Fq "$marker" "$backup/cron-before"; then
  cp "$backup/cron-before" "$backup/cron-proposed"
  printf '4,19,34,49 * * * * /usr/bin/flock -n %s/master-cycle.lock /usr/bin/timeout 130s /bin/bash %s/run-f41-queue.sh >> %s/f41-private-queue.log 2>&1 # %s\n' "$master" "$master" "$master" "$marker" >> "$backup/cron-proposed"
  crontab - < "$backup/cron-proposed"
fi
test "$(crontab -l | grep -Fc "$marker")" -eq 1
test "$(crontab -l | grep -c SAEIT_MASTER_AGENT_V1)" -eq 2
echo F41_MOJ1RO1_PRIVATE_QUEUE_ON_VPS=PASS
echo F41_MOJ1RO1_RECURRING_15MIN_SCAN=ACTIVE
echo F41_PAYMENT_AND_MAINNET_ACTIONS=0
echo F41_INDEPENDENT_QUALITY_1000=false
echo F41_SITE_CHANGES=0
echo F41_MASTER_SAFE_BACKUP="$backup"
