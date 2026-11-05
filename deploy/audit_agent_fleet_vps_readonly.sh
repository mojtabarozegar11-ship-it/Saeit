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

# Inspect only the two previously observed factory backlog owners. Do not
# read task payloads or change their states; this identifies missing dispatch
# routes without pretending that a DB row is an operating agent.
"$python_bin" - <<'PY'
import hashlib
import json
import re

import django
django.setup()

from django.db import connection
from django.db.models import Count
from core.models import Agent, AgentTask, AgentCapability
from core.agent_registry import AgentRegistry
from core.economic_tool_pack import build_economic_gateway
from core.services import normalize_action

owners = ("factory-market-research-agent", "factory-opportunity-validation-agent")
tables = set(connection.introspection.table_names())
required = {
    Agent._meta.db_table, AgentTask._meta.db_table,
    AgentCapability._meta.db_table,
    AgentCapability.agents.through._meta.db_table,
}
if not required.issubset(tables):
    print("AGENT_FLEET_FACTORY_QUEUE_ROUTES=" + json.dumps({
        "status": "schema_unavailable", "missing_table_count": len(required - tables),
        "writes": 0, "execution_verified": False,
    }, sort_keys=True))
else:
    gateway_codes = set(build_economic_gateway().describe())
    registry = AgentRegistry()
    agents = {a.code: a for a in Agent.objects.filter(code__in=owners)}
    groups = list(
        AgentTask.objects.filter(agent__code__in=owners)
        .values("agent__code", "status", "action_type", "capability_code")
        .annotate(count=Count("pk"))
        .order_by("agent__code", "status", "action_type", "capability_code")
    )
    def safe_code(value):
        val = str(value or "")
        if re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_-]{0,79}", val):
            return val
        return "sha256:" + hashlib.sha256(val.encode()).hexdigest()[:12]

    rows = []
    for group in groups:
        owner = agents.get(group["agent__code"])
        action = normalize_action(group["action_type"])
        cap = registry.capability_for(owner, group["action_type"]) if owner else None
        grant_matches_snapshot = bool(
            cap and (not group["capability_code"] or cap.code == group["capability_code"])
        )
        registered_tool = action in gateway_codes
        rows.append({
            "agent": safe_code(group["agent__code"]),
            "status": safe_code(group["status"]),
            "action": safe_code(group["action_type"]),
            "capability": safe_code(group["capability_code"]),
            "count": group["count"],
            "agent_active": bool(owner and owner.active),
            "active_grant_matches_snapshot": grant_matches_snapshot,
            "economic_gateway_tool_present": registered_tool,
            "candidate_for_economic_gateway": bool(
                owner and owner.active and grant_matches_snapshot and registered_tool
                and group["status"] == "queued"
            ),
        })
    print("AGENT_FLEET_FACTORY_QUEUE_ROUTES=" + json.dumps({
        "status": "read_only", "owners": list(owners),
        "total_tasks": sum(row["count"] for row in rows),
        "queued_tasks": sum(row["count"] for row in rows if row["status"] == "queued"),
        "grouped_routes": rows, "writes": 0,
        "execution_verified": False,
        "scope": "economic_gateway_only; other workers not assessed",
    }, sort_keys=True, separators=(",", ":")))
PY

# Distinguish a historical backlog from a live, executable queue. Installed
# factory code can differ from the repository, so inspect bounded live evidence
# without claiming a worker from a mere filename or process-name match.
"$python_bin" - <<'PY'
import collections
import hashlib
import json
from datetime import timedelta
from pathlib import Path

import django
django.setup()

from django.apps import apps
from django.utils import timezone

Task = apps.get_model("core", "AgentTask")
Run = apps.get_model("core", "FactoryRun")
Product = apps.get_model("core", "Product")
now = timezone.now()
owners = ("factory-market-research-agent", "factory-opportunity-validation-agent")
open_statuses = ("queued", "running", "blocked")
fields = {field.name for field in Task._meta.fields}
has_run_link = "factory_run" in fields
active_run_ids = set(Run.objects.filter(status="active").values_list("pk", flat=True))

def age_hours(value):
    return max(0, int((now - value).total_seconds() // 3600)) if value else None

def reason_group(output):
    if not isinstance(output, dict):
        return "no_structured_reason"
    # Never emit arbitrary task error text or inputs. These are merely
    # diagnostic categories; they do not confer approval to resume a task.
    value = str(output.get("error") or output.get("reason") or "").lower()
    for category, terms in (
        ("owner_or_approval", ("owner", "approval", "provenance", "permission")),
        ("budget_or_capacity", ("budget", "capacity", "quota", "cost")),
        ("research_or_evidence", ("research", "source", "evidence", "citation")),
        ("retry_or_timeout", ("retry", "timeout", "stale", "lock")),
        ("configuration", ("config", "provider", "credential", "missing")),
    ):
        if any(term in value for term in terms):
            return category
    return "other_or_unrecorded"

rows = []
for owner in owners:
    tasks = Task.objects.filter(agent__code=owner)
    recent = {
        "completed_last_hour": tasks.filter(status="completed", updated_at__gte=now-timedelta(hours=1)).count(),
        "completed_last_day": tasks.filter(status="completed", updated_at__gte=now-timedelta(days=1)).count(),
        "completed_last_week": tasks.filter(status="completed", updated_at__gte=now-timedelta(days=7)).count(),
    }
    counts = collections.Counter()
    reasons = collections.Counter()
    links = collections.Counter()
    ages = collections.defaultdict(list)
    attempt_exhausted = collections.Counter()
    for task in tasks.filter(status__in=open_statuses).only(
        "status", "created_at", "updated_at", "attempt_count", "max_attempts",
        "output_data", *( ["factory_run"] if has_run_link else [] )
    ).iterator(chunk_size=200):
        counts[task.status] += 1
        ages[task.status].append(age_hours(task.created_at))
        if task.attempt_count >= task.max_attempts:
            attempt_exhausted[task.status] += 1
        if task.status == "blocked":
            reasons[reason_group(task.output_data)] += 1
        if has_run_link:
            link = task.factory_run_id
            links["unlinked" if link is None else
                  "linked_active_run" if link in active_run_ids else "linked_nonactive_run"] += 1
    rows.append({
        "agent": owner, "open_counts": dict(sorted(counts.items())),
        "oldest_open_age_hours": {key: max(values) for key, values in ages.items() if values},
        "attempt_budget_exhausted": dict(sorted(attempt_exhausted.items())),
        "blocked_reason_categories": dict(sorted(reasons.items())),
        "factory_run_links": dict(sorted(links.items())) if has_run_link else "field_absent",
        **recent,
    })

base = Path.home() / "factory-runtime"
known_sources = {
    "factory_staging_tick": base / "django-app/core/management/commands/factory_staging_tick.py",
    "factory_agent_runtime": base / "django-app/core/factory_agent_runtime.py",
    "factory_stage4": base / "django-app/core/factory_stage4.py",
    "native_factory_loop": base / "operations/vps-only-loop.sh",
    "stage4_due_dispatch": base / "operations/stage4-due-dispatch.py",
}
sources = {}
for label, path in known_sources.items():
    if path.is_symlink():
        sources[label] = {"state": "unsafe_symlink"}
    elif not path.is_file():
        sources[label] = {"state": "absent"}
    elif path.stat().st_size > 300000:
        sources[label] = {"state": "oversized_not_inspected"}
    else:
        data = path.read_bytes()
        sources[label] = {
            "state": "present", "sha256_prefix": hashlib.sha256(data).hexdigest()[:16],
            "mentions_research": b"product_research" in data,
            "mentions_validation": b"product_validation" in data,
            "mentions_worker_runner": b"WorkerRunner" in data,
            "mentions_task_runtime": b"TaskRuntime" in data,
        }

print("AGENT_FLEET_FACTORY_BACKLOG_EXECUTION_EVIDENCE=" + json.dumps({
    "schema": "saeit.factory.agent-backlog-execution-evidence.v1",
    "read_only": True, "utc": now.isoformat(),
    "active_factory_runs": len(active_run_ids),
    "active_django_products": Product.objects.filter(active=True).count(),
    "task_factory_run_field_present": has_run_link,
    "agents": rows, "installed_source_indicators": sources,
    "worker_execution_proven": False,
    "blocked_tasks_resumed": 0, "tasks_modified": 0,
}, sort_keys=True, separators=(",", ":")))
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
