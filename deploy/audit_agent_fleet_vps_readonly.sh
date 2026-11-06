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

# Distinguish internally completed economic tasks from customer-facing output.
# Only aggregate known status/action/evidence markers; never emit task inputs,
# receipts, customer identifiers or amounts. This does not reconcile payments.
"$python_bin" - <<'PY'
import collections
import hashlib
import json
from datetime import timedelta
from pathlib import Path

import django
django.setup()

from django.db import connection
from django.utils import timezone
from core.models import AgentTask, Order, LedgerEntry, Product

now = timezone.now()
windows = {"day": now - timedelta(days=1),
           "week": now - timedelta(days=7),
           "month": now - timedelta(days=30)}
tasks = AgentTask.objects.filter(agent__code="economic-master-agent")
counts = {key: collections.Counter() for key in windows}
evidence_kinds = collections.Counter()
outputs = collections.Counter()
latest_completion = None
for task in tasks.filter(updated_at__gte=windows["month"]).only(
    "status", "action_type", "updated_at", "output_data"
).iterator(chunk_size=200):
    action = task.action_type if task.action_type in {
        "income_market_research", "income_opportunity_score", "income_offer_design",
        "income_mvp_build", "income_growth_experiment", "income_revenue_verify",
        "income_profit_optimize", "master_self_improvement",
    } else "other"
    for label, cutoff in windows.items():
        if task.updated_at >= cutoff:
            counts[label][(task.status, action)] += 1
    if task.status != "completed":
        continue
    if latest_completion is None or task.updated_at > latest_completion:
        latest_completion = task.updated_at
    data = task.output_data if isinstance(task.output_data, dict) else {}
    outputs["completed"] += 1
    if data.get("verified_effect") is True:
        outputs["internally_marked_verified_effect"] += 1
    if data.get("verified_revenue") is not None:
        outputs["non_null_revenue_claims_without_provider_check"] += 1
    validation = data.get("market_validation")
    if isinstance(validation, dict) and validation.get("status") == "independently_verified":
        outputs["internally_tagged_market_validation"] += 1
    evidence = data.get("evidence")
    kind = evidence.get("kind") if isinstance(evidence, dict) else None
    if kind in {"database_measurement", "product_inventory", "product_record",
                "mvp_asset", "growth_experiment", "internal_ledger_inventory",
                "profit_baseline", "production_gate"}:
        evidence_kinds[kind] += 1
    elif kind:
        evidence_kinds["other"] += 1
    else:
        evidence_kinds["none"] += 1

tables = set(connection.introspection.table_names())
def safe_count(model, filter_kwargs=None):
    if model._meta.db_table not in tables:
        return None
    qs = model.objects
    return qs.filter(**filter_kwargs).count() if filter_kwargs else qs.count()

app = Path.home() / "factory-runtime/django-app/core"
installed_source = {}
for label, name in (("economic_brain", "autonomous_brain.py"),
                    ("economic_tools", "economic_tool_pack.py")):
    path = app / name
    if path.is_file() and not path.is_symlink() and path.stat().st_size < 200000:
        data = path.read_bytes()
        installed_source[label] = {
            "state": "present", "sha256_prefix": hashlib.sha256(data).hexdigest()[:16],
            "contains_external_demand_guard": b"await_external_market_evidence" in data,
            "contains_unreconciled_revenue_guard": b"external_settlement_evidence_required" in data,
        }
    else:
        installed_source[label] = {"state": "unavailable_or_unsafe"}

print("AGENT_FLEET_ECONOMIC_OUTCOME_EVIDENCE=" + json.dumps({
    "schema": "saeit.agent.economic-outcome.v1", "read_only": True,
    "counts": {label: [
        {"status": status, "action": action, "count": value}
        for (status, action), value in sorted(groups.items())
    ] for label, groups in counts.items()},
    "last_completed_age_hours": (
        int((now - latest_completion).total_seconds() // 3600)
        if latest_completion else None
    ),
    "completion_evidence_kinds": dict(sorted(evidence_kinds.items())),
    "output_flags": dict(sorted(outputs.items())),
    "active_django_products": safe_count(Product, {"active": True}),
    "orders_total": safe_count(Order),
    "paid_or_completed_orders": safe_count(Order, {"status__in": ("paid", "completed")}),
    "ledger_payment_events": safe_count(LedgerEntry, {"entry_type": "payment"}),
    "ledger_settlement_candidates": safe_count(LedgerEntry, {"entry_type": "settlement"}),
    "provider_settlement_reconciliation_performed_by_audit": False,
    "installed_source": installed_source,
    "task_mutations": 0, "external_messages_sent": 0,
}, sort_keys=True, separators=(",", ":")))
PY

# Determine whether apparent profit-optimization churn is still happening,
# when its tasks were created, and which permitted task-planning path created
# them.  Never print task identifiers, raw JSON payloads or customer data.
"$python_bin" - <<'PY'
import collections
import hashlib
import json
from datetime import timedelta
from pathlib import Path

import django
django.setup()

from django.utils import timezone
from core.models import AgentTask

now = timezone.now()
qs = AgentTask.objects.filter(
    agent__code="economic-master-agent",
    action_type="income_profit_optimize",
).order_by("-created_at")

def age_bucket(value):
    hours = max(0, (now - value).total_seconds() / 3600)
    if hours < 1: return "under_1h"
    if hours < 6: return "1_to_6h"
    if hours < 12: return "6_to_12h"
    if hours < 24: return "12_to_24h"
    if hours < 72: return "1_to_3d"
    if hours < 168: return "3_to_7d"
    return "over_7d"

creation = collections.Counter()
completion = collections.Counter()
origin = collections.Counter()
last_created = None
last_completed = None
for task in qs.filter(created_at__gte=now-timedelta(days=7)).only(
    "created_at", "updated_at", "input_data", "status"
).iterator(chunk_size=200):
    if last_created is None or task.created_at > last_created:
        last_created = task.created_at
    creation[age_bucket(task.created_at)] += 1
    data = task.input_data if isinstance(task.input_data, dict) else {}
    if isinstance(data.get("brain_decision"), dict):
        origin["brain_decision"] += 1
    elif "replanned_from" in data:
        origin["replanned_prerequisite"] += 1
    else:
        origin["no_brain_decision_marker"] += 1
    if task.status == "completed":
        completion[age_bucket(task.updated_at)] += 1
        if last_completed is None or task.updated_at > last_completed:
            last_completed = task.updated_at

root = Path.home() / "factory-runtime/django-app/core/management/commands"
source = {}
for label, name in (("online_income_cycle", "online_income_cycle.py"),
                    ("autonomous_master_loop", "autonomous_master_loop.py")):
    file = root / name
    if file.is_file() and not file.is_symlink() and file.stat().st_size < 100000:
        source[label] = hashlib.sha256(file.read_bytes()).hexdigest()[:16]
    else:
        source[label] = "unavailable_or_unsafe"

print("AGENT_FLEET_PROFIT_CHURN_PROVENANCE="+json.dumps({
    "schema":"saeit.agent.profit-churn.v1", "read_only":True,
    "profit_tasks_created_by_age_bucket_7d":dict(sorted(creation.items())),
    "profit_tasks_completed_by_age_bucket_7d":dict(sorted(completion.items())),
    "creation_origin_marker_7d":dict(sorted(origin.items())),
    "latest_creation_age_minutes": (
        int((now-last_created).total_seconds()//60) if last_created else None),
    "latest_completion_age_minutes": (
        int((now-last_completed).total_seconds()//60) if last_completed else None),
    "installed_entrypoint_sha256_prefix":source,
    "task_mutations":0, "cron_mutations":0,
},sort_keys=True,separators=(",",":")))
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

# Inspect a bounded set of installed Django and factory Python modules to find
# any dedicated executor candidates; do not invoke tasks or scan private data.
"$python_bin" - <<'PY'
import hashlib
import json
from pathlib import Path

import django
django.setup()

from django.apps import apps
from django.core.management import get_commands

app = Path.home() / "factory-runtime/django-app"
roots = (
    ("core_modules", app / "core"),
    ("core_commands", app / "core/management/commands"),
    ("project_scripts", app / "scripts"),
    ("runtime_scripts", Path.home() / "factory-runtime/scripts"),
)
needles = {
    "product_research": b"product_research",
    "product_validation": b"product_validation",
    "agent_task_model": b"AgentTask",
    "worker_runner": b"WorkerRunner",
    "task_runtime": b"TaskRuntime",
}
scanned = 0
skipped = 0
hits = []
for label, root in roots:
    if not root.is_dir() or root.is_symlink():
        continue
    for path in sorted(root.glob("*.py"))[:300]:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 350000:
            skipped += 1
            continue
        scanned += 1
        source = path.read_bytes()
        flags = {key: value in source for key, value in needles.items()}
        if flags["product_research"] or flags["product_validation"]:
            hits.append({"root":label, "module":path.stem,
                         "flags":flags,
                         "sha256_prefix":hashlib.sha256(source).hexdigest()[:16]})

run = apps.get_model("core", "FactoryRun")
product = apps.get_model("core", "Product")
task = apps.get_model("core", "AgentTask")
run_fields = {field.name for field in run._meta.fields}
task_fields = {field.name for field in task._meta.fields}
active_runs = run.objects.filter(status="active")
if "product" in run_fields:
    active_run_product_status = {
        "product_active":active_runs.filter(product__active=True).count(),
        "product_inactive":active_runs.filter(product__active=False).count(),
        "product_missing":active_runs.filter(product__isnull=True).count(),
    }
else:
    active_run_product_status = {"unknown_missing_product_relation":active_runs.count()}

commands = sorted(name for name in get_commands() if any(
    term in name for term in ("factory", "product", "economic", "worker", "research", "validation")
))
model_source = app / "core/models.py"
model_sha = None
model_declares_run = None
if model_source.is_file() and not model_source.is_symlink() and model_source.stat().st_size < 350000:
    code = model_source.read_bytes()
    model_sha = hashlib.sha256(code).hexdigest()[:16]
    model_declares_run = b"class FactoryRun" in code

print("AGENT_FLEET_INSTALLED_EXECUTOR_DISCOVERY="+json.dumps({
    "schema":"saeit.agent.installed-executor-discovery.v1",
    "read_only":True,
    "source_scope":"direct Python modules only in known Django core and factory scripts",
    "files_scanned":scanned,"files_skipped":skipped,
    "candidate_source_count":len(hits),"candidate_sources":hits[:50],
    "candidate_sources_truncated":len(hits)>50,
    "installed_command_candidates":commands[:80],
    "installed_commands_truncated":len(commands)>80,
    "django_factory_run_model_present":True,
    "django_task_has_factory_run_relation":"factory_run" in task_fields,
    "active_runs_by_product_status":active_run_product_status,
    "live_models_sha256_prefix":model_sha,
    "live_models_declares_factory_run_class":model_declares_run,
    "task_mutations":0,"service_mutations":0,
},sort_keys=True,separators=(",",":")))
PY

# Distinguish a historical backlog from a live, executable queue. Installed
# factory code can differ from the repository, so inspect bounded live evidence
# without claiming a worker from a mere filename or process-name match.
"$python_bin" - <<'PY'
import ast
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
has_run_product = any(field.name == "product" for field in Run._meta.fields)
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
        "queued_on_active_django_products": (
            tasks.filter(status="queued", factory_run__product__active=True).count()
            if has_run_link and has_run_product else None
        ),
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
        try:
            parsed = ast.parse(data, filename=label)
            dispatch_functions = sorted(set(
                node.name for node in ast.walk(parsed)
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and any(tag in node.name.lower() for tag in
                        ("worker", "dispatch", "research", "validat", "task", "staging"))
            ))[:20]
        except (SyntaxError, UnicodeDecodeError):
            dispatch_functions = []
        sources[label] = {
            "state": "present", "sha256_prefix": hashlib.sha256(data).hexdigest()[:16],
            "mentions_research": b"product_research" in data,
            "mentions_validation": b"product_validation" in data,
            "mentions_worker_runner": b"WorkerRunner" in data,
            "mentions_task_runtime": b"TaskRuntime" in data,
            "candidate_function_names": dispatch_functions,
        }

print("AGENT_FLEET_FACTORY_BACKLOG_EXECUTION_EVIDENCE=" + json.dumps({
    "schema": "saeit.factory.agent-backlog-execution-evidence.v1",
    "read_only": True, "utc": now.isoformat(),
    "active_factory_runs": len(active_run_ids),
    "active_django_products": Product.objects.filter(active=True).count(),
    "task_factory_run_field_present": has_run_link,
    "factory_run_product_field_present": has_run_product,
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
    route_flags = {
        "factory_agent_runtime": "factory_agent_runtime" in command,
        "factory_staging_tick": "factory_staging_tick" in command,
        "stage4_due_dispatch": "stage4-due-dispatch" in command or "stage4_due_dispatch" in command,
        "economic_worker": "economic_worker" in command,
    }
    entries.append({"schedule": schedule, "marker": markers[-1] if markers else None,
                    "command_sha256": hashlib.sha256(command.encode()).hexdigest()[:16],
                    "route_flags": route_flags})
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
