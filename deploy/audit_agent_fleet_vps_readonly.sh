#!/usr/bin/env bash
# Read-only live VPS agent inventory. Does not change cron, code, or database.
set -euo pipefail
umask 077

test "$(id -un)" = githubops || { echo AGENT_AUDIT_WRONG_USER; exit 2; }
base="$HOME/factory-runtime"
app="$base/django-app"
python_bin="$base/.venv/bin/python"
test -x "$python_bin" && test -f "$app/manage.py" || {
  echo AGENT_AUDIT_RUNTIME_NOT_FOUND; exit 2;
}
command -v crontab >/dev/null && command -v ps >/dev/null || {
  echo AGENT_AUDIT_TOOLS_MISSING; exit 2;
}

export SAEIT_ENV=production MOJ_FACTORY_LOCAL_MODE=1 DJANGO_SETTINGS_MODULE=config.settings
export MOJ_PAID_LLM_ENABLED=0 MOJ_LLM_DAILY_CALL_BUDGET=0 MOJ_LLM_MAX_COST_MINOR=0
cd "$app"

echo AGENT_FLEET_DATABASE_PREVIEW_BEGIN
"$python_bin" - <<'PY'
import json
from datetime import timedelta

import django
django.setup()

from django.db import connection
from django.utils import timezone
from core.models import Agent, AgentTask

tables = set(connection.introspection.table_names())
assert Agent._meta.db_table in tables, "AGENT_FLEET_AGENT_TABLE_MISSING"
assert AgentTask._meta.db_table in tables, "AGENT_FLEET_TASK_TABLE_MISSING"
fields = {f.name for f in AgentTask._meta.fields}
cutoff = timezone.now() - timedelta(days=30)
protected = {"economic-master-agent", "moj_1ro_1",
             "content-director", "knowledge-content-director"}
legacy = {"core_research", "newsletter-specialist",
          "newsletter-company-news", "newsletter-world-watch",
          "newsletter-unit-reports"}
active_statuses = {"queued", "running", "blocked"}
pending_story_statuses = {"draft", "approved", "scheduled",
                          "review", "queued", "processing"}

rows = []
for agent in Agent.objects.all().order_by("code").iterator():
    tasks = AgentTask.objects.filter(agent=agent)
    active_tasks = tasks.filter(status__in=active_statuses).count()
    recent_completed = (tasks.filter(status="completed", updated_at__gte=cutoff).count()
                        if "updated_at" in fields else None)
    capabilities = getattr(agent, "capabilities", None)
    unique_capabilities = None
    if capabilities is not None:
        capability_model = capabilities.model
        join_table = capability_model.agents.through._meta.db_table
        if capability_model._meta.db_table in tables and join_table in tables:
            unique_capabilities = [
                cap.code for cap in capabilities.filter(active=True)
                if not cap.agents.filter(active=True).exclude(pk=agent.pk).exists()
            ]
    # A missing newsletter relation means its dependencies cannot be certified.
    newsletter_relation = getattr(agent, "newsletter_stories", None)
    pending_stories = pending_distributions = recent_publications = None
    if (newsletter_relation is not None and newsletter_relation.model._meta.db_table in tables):
        pending_stories = newsletter_relation.filter(
            status__in=pending_story_statuses).count()
        pending_distributions = newsletter_relation.filter(
            publications__status__in=("queued", "blocked")).distinct().count()
        recent_publications = newsletter_relation.filter(
            status="published", published_at__gte=cutoff).count()

    if agent.code in protected:
        decision = "retain_protected"
    elif not agent.active:
        decision = "already_inactive"
    elif active_tasks or pending_stories or pending_distributions:
        decision = "retain_active_dependency"
    elif recent_completed or recent_publications:
        decision = "review_recent_output"
    elif unique_capabilities:
        decision = "review_unique_capability"
    elif (agent.code in legacy and pending_stories is not None
          and unique_capabilities is not None and recent_completed is not None):
        # Only a *candidate*: external schedules and integrations still matter.
        decision = "candidate_legacy_dependency_review"
    else:
        decision = "review_unverified_external_dependency"
    rows.append({
        "code": agent.code, "active": agent.active, "decision": decision,
        "active_tasks": active_tasks, "recent_completed_tasks": recent_completed,
        "pending_stories": pending_stories, "pending_distributions": pending_distributions,
        "recent_publications": recent_publications,
        "unique_active_capabilities": unique_capabilities,
    })
summary = {
    "total": len(rows),
    "active": sum(row["active"] for row in rows),
    "candidates_not_authorized_to_retire": sum(
        row["decision"] == "candidate_legacy_dependency_review" for row in rows),
    "active_tasks": sum(row["active_tasks"] for row in rows),
    "database_only": True,
    "writes": 0,
}
print("AGENT_FLEET_DATABASE_PREVIEW=" +
      json.dumps({"summary": summary, "agents": rows}, sort_keys=True, separators=(",", ":")))
PY

# Never print crontab commands, inline environment values, or process arguments.
"$python_bin" - <<'PY'
import hashlib
import json
import re
import subprocess

cron = subprocess.run(["crontab", "-l"], capture_output=True, text=True, timeout=12)
if cron.returncode not in (0, 1):
    raise RuntimeError("AGENT_FLEET_CRON_UNREADABLE")
entries = []
for line in cron.stdout.splitlines():
    line = line.strip()
    if not line or line.startswith("#") or line.startswith("@") or "=" in line.split()[0]:
        continue
    parts = line.split(maxsplit=5)
    if len(parts) != 6:
        continue
    schedule, command = " ".join(parts[:5]), parts[5]
    # A stable command fingerprint permits duplicates to be located without
    # disclosing URLs, inline secrets, personal paths or command arguments.
    markers = re.findall(r"#\s*([A-Z][A-Z0-9_-]{5,})\s*$", command)
    entries.append({"schedule": schedule, "marker": markers[-1] if markers else None,
                    "command_sha256": hashlib.sha256(command.encode()).hexdigest()[:16]})
print("AGENT_FLEET_USER_CRON=" + json.dumps({"readable": cron.returncode == 0,
    "entries": entries}, sort_keys=True, separators=(",", ":")))

ps = subprocess.run(["ps", "-eo", "args="], capture_output=True, text=True, timeout=12, check=True)
needles = ("autonomous_master_loop", "online_income_cycle", "factory", "newsletter", "mojtrade", "mpw_")
counts = {name: 0 for name in needles}
for command in ps.stdout.splitlines():
    # Keep only counts; no process arguments leave the VPS.
    for name in needles:
        if name in command:
            counts[name] += 1
print("AGENT_FLEET_PROCESS_MATCH_COUNTS=" + json.dumps(counts, sort_keys=True, separators=(",", ":")))
PY
echo AGENT_FLEET_AUDIT_READ_ONLY_COMPLETE
