#!/usr/bin/env bash
# On SUCCESSFUL private six-family native acceptance only, dispatch one
# authenticated moj_1ro_1 QA batch for THAT exact source version.
# Never touches cPanel, stores, wallet, finance or certifying identities.
set -euo pipefail
umask 077
test "${GITHUB_REPOSITORY:-}" = "mojtabarozegar11-ship-it/Saeit"
test "${GITHUB_REF:-}" = "refs/heads/main"
test -n "${VPS_KEY:-}" && test "$#" -eq 1
run="$1"
[[ "$run" =~ ^[0-9]{5,18}-[0-9]{1,3}$ ]]
work="$(mktemp -d)"
chmod 700 "$work"
trap 'rm -rf -- "$work"' EXIT
printf '%s' "$VPS_KEY" | python3 -c 'import sys;s=sys.stdin.buffer.read().decode("utf8");s=s.replace("\r\n","\n").replace("\r","").replace("\\n","\n").rstrip()+"\n";sys.stdout.buffer.write(s.encode())' > "$work/key"
chmod 600 "$work/key"
ssh-keygen -y -P '' -f "$work/key" >/dev/null
ssh-keyscan -T 10 -t rsa 178.239.147.150 > "$work/known" 2>/dev/null
test "$(ssh-keygen -lf "$work/known" -E sha256 | awk '{print $2}' | sort -u)" = "SHA256:AYdzF3K5uSwAXElE1w/dKo04iT2BbMGwHbRA2Cu4rrs"
opts=(-i "$work/key" -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes
      -o UserKnownHostsFile="$work/known" -o BatchMode=yes
      -o ConnectTimeout=15 -o ServerAliveInterval=10)
host="githubops@178.239.147.150"
ssh -T "${opts[@]}" "$host" "bash -se -- '$run'" <<'REMOTE'
set -euo pipefail
umask 077
test "$(id -un)" = githubops && test "$#" -eq 1
run="$1"
[[ "$run" =~ ^[0-9]{5,18}-[0-9]{1,3}$ ]]
base="$HOME/factory-runtime"
private="$base/private/autonomous-product-cycle"
master="$base/operations/master-agent"
py="$base/.venv/bin/python"
test -x "$py" && test -x "$master/run-native-qa.sh"
test -s "$private/native-candidate-evidence/$run/verified-six-private-native.json"
test -s "$private/quality-excellence/six-native-rework/$run/review.json"
export SAEIT_ENV=production MOJ_FACTORY_LOCAL_MODE=1 DJANGO_SETTINGS_MODULE=config.settings
export MOJ_PAID_LLM_ENABLED=0 MOJ_LLM_DAILY_CALL_BUDGET=0 MOJ_LLM_MAX_COST_MINOR=0
cd "$base/django-app"
"$py" -B - "$run" "$private" <<'PY'
import sys
from pathlib import Path
from core.factory_native_review_gateway import latest_snapshot,snapshot,digest
run=sys.argv[1];root=Path(sys.argv[2])
data=snapshot(root,run)
assert data["reviewed_families"]==6 and data["verified_native_candidate_files"]==56
assert data["completed_professional_quality_1000_certifications"]==0
if latest_snapshot(root)!=run:
    # Do not incorrectly attribute a NEWER batch to an old run.
    # Cron will pick up the latest; this old verified run can still
    # be handled idempotently by its own previous completed tasks.
    print("MOJ1RO1_NATIVE_TRIGGERED_BATCH_SUPERSEDED")
    sys.exit(3)
print("MOJ1RO1_NATIVE_TRIGGER_BOUND_REVIEW_SHA256="+digest(
    root/"quality-excellence/six-native-rework"/run/"review.json"))
PY
status=$?
if test "$status" -eq 3; then
    echo MOJ1RO1_NATIVE_TRIGGER_SUPERSEDED_PRIVATE_NO_WRITE
    exit 0
fi
test "$status" -eq 0
# The production economic master already uses this flock; do not race it.
flock -w 100 "$master/master-cycle.lock" timeout 175s "$master/run-native-qa.sh"
"$py" -B - "$run" "$private" <<'PY'
import django,sys
django.setup()
from pathlib import Path
from core.models import Agent,AgentTask,AuditLog
from core.factory_native_review_gateway import snapshot,digest
run=sys.argv[1];root=Path(sys.argv[2]);data=snapshot(root,run)
agent=Agent.objects.get(code="moj_1ro_1",active=True)
assert set(agent.capabilities.filter(active=True).values_list("code",flat=True))=={"factory_native_review"}
tasks=list(AgentTask.objects.filter(agent=agent,action_type="factory_native_review",
            input_data__source_run=run).order_by("pk"))
assert len(tasks)==6 and {t.input_data["family"] for t in tasks}=={
    "F12","F13","F14","F16","F17","F26"}
review_hash=digest(root/"quality-excellence/six-native-rework"/run/"review.json")
assert all(t.status=="completed" and t.execution_id
           and t.input_data["review_sha256"]==review_hash
           and t.output_data.get("source_review_sha256")==review_hash
           and t.output_data.get("verified_effect") is True
           and t.output_data.get("quality_1000_certified") is False
           and t.output_data.get("commercial_release") is False for t in tasks)
audits=AuditLog.objects.filter(actor_type="agent",actor_id=str(agent.pk),
        action="tool_invocation_completed",target_type="AgentTask",
        target_id__in=[str(t.pk) for t in tasks]).count()
assert audits>=6
print("MOJ1RO1_POST_NATIVE_GENUINE_TASKS=6")
print("MOJ1RO1_POST_NATIVE_VERIFIED_AUDITS="+str(audits))
print("MOJ1RO1_POST_NATIVE_PRIVATE_REVIEW_SHA256="+review_hash)
print("MOJ1RO1_POST_NATIVE_EXTERNAL_REVIEW_GATES="+str(
    data["specialist_or_physical_review_needed"]))
print("MOJ1RO1_POST_NATIVE_PROFESSIONAL_QUALITY_1000=0")
print("MOJ1RO1_POST_NATIVE_WEBSITE_WRITES=0")
PY
REMOTE
