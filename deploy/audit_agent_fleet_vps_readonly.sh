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

# Run the source-level fleet audit against the live database before the
# broader compatibility inventory. The command is strictly read-only and
# emits no task payloads, identifiers, messages or financial data.
echo AGENT_FLEET_COMMAND_AUDIT_BEGIN
"$python_bin" manage.py audit_agent_fleet --days 30 --stale-after 900
echo AGENT_FLEET_COMMAND_AUDIT_END

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

# Trace the actual installed factory command path and its open-task product
# relationships. File contents and individual task payloads remain private.
"$python_bin" - <<'PY'
import ast
import collections
import hashlib
import json
from pathlib import Path

import django
django.setup()
from django.apps import apps
from django.db.models import Count

app = Path.home() / "factory-runtime/django-app/core"
modules = {
    "factory_command": app / "management/commands/factory_product_step.py",
    "factory_tools": app / "factory_tool_pack.py",
    "factory_governance": app / "factory_governance.py",
    "factory_runtime": app / "factory_agent_runtime.py",
}
route_call_names = {
    "run", "execute", "handle", "claim", "complete", "fail", "invoke",
    "plan_product_factory_step", "decide_product_factory_step",
    "create", "call_command", "factory_product_step", "run_factory_step",
    "build_factory_gateway", "build_economic_gateway", "select_for_update",
}
module_flags = {}
for label, path in modules.items():
    if not path.is_file() or path.is_symlink() or path.stat().st_size > 350000:
        module_flags[label] = {"state":"unavailable_or_unsafe"}
        continue
    data = path.read_bytes()
    tree = ast.parse(data, filename=path.name)
    direct_functions = sorted({node.name for node in tree.body
                               if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef))})
    class_methods = sorted({node.name for cls in tree.body if isinstance(cls,ast.ClassDef)
                            for node in cls.body if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef))})
    calls = set()
    for node in ast.walk(tree):
        if isinstance(node,ast.Call):
            name = node.func.attr if isinstance(node.func,ast.Attribute) else (
                node.func.id if isinstance(node.func,ast.Name) else "")
            if name in route_call_names:
                calls.add(name)
    module_flags[label] = {
        "state":"present","sha256_prefix":hashlib.sha256(data).hexdigest()[:16],
        "direct_functions":direct_functions[:35],
        "class_methods":class_methods[:35],
        "known_dispatch_calls":sorted(calls),
        "mentions_worker_runner":b"WorkerRunner" in data,
        "mentions_task_runtime":b"TaskRuntime" in data,
    }

Task = apps.get_model("core", "AgentTask")
groups = collections.Counter()
rows = Task.objects.filter(
    agent__code__in=("factory-market-research-agent", "factory-opportunity-validation-agent"),
    status__in=("queued", "blocked"),
).values(
    "action_type", "status", "factory_run__status",
    "factory_run__product_id", "factory_run__product__active"
).annotate(count=Count("pk"))
for row in rows:
    if row["factory_run__status"] is None:
        relation = "no_run"
    elif row["factory_run__status"] != "active":
        relation = "inactive_run"
    elif row["factory_run__product_id"] is None:
        relation = "active_run_no_product"
    elif row["factory_run__product__active"]:
        relation = "active_run_active_product"
    else:
        relation = "active_run_inactive_product"
    groups[(row["action_type"],row["status"],relation)] += row["count"]

print("AGENT_FLEET_FACTORY_DISPATCH_TRACE="+json.dumps({
    "schema":"saeit.agent.factory-dispatch-trace.v1", "read_only":True,
    "installed_module_routes":module_flags,
    "open_task_run_product_relationships":[
        {"action":action,"status":status,"relation":relation,"count":count}
        for (action,status,relation),count in sorted(groups.items())],
    "tasks_executed":0,"tasks_modified":0,
},sort_keys=True,separators=(",",":")))
PY

# Check whether the live-only factory command can resolve its planning method
# and whether the dedicated gateway actually registers both queued actions.
"$python_bin" - <<'PY'
import ast
import json
from pathlib import Path

import django
django.setup()
from core.autonomous_brain import AutonomousBrain
from core.factory_tool_pack import build_factory_gateway

root = Path.home() / "factory-runtime/django-app/core"
command_path = root / "management/commands/factory_product_step.py"
if not command_path.is_file() or command_path.is_symlink() or command_path.stat().st_size > 350000:
    raise RuntimeError("FACTORY_COMMAND_SOURCE_UNAVAILABLE")
tree = ast.parse(command_path.read_text(encoding="utf-8"))
imports = []
arguments = []
call_sites = []
constructor_bindings = []
for node in ast.walk(tree):
    if isinstance(node,ast.ImportFrom) and node.module and node.module.startswith("core"):
        imports.append({"module":node.module,"names":sorted(alias.name for alias in node.names)[:12]})
    if isinstance(node,ast.Call):
        name = node.func.attr if isinstance(node.func,ast.Attribute) else (
            node.func.id if isinstance(node.func,ast.Name) else "")
        if name == "add_argument":
            arguments.extend(arg.value for arg in node.args if isinstance(arg,ast.Constant)
                             and isinstance(arg.value,str) and arg.value.startswith("--"))
        if name in ("plan_product_factory_step", "decide_product_factory_step", "run"):
            receiver = node.func.value if isinstance(node.func,ast.Attribute) else None
            if isinstance(receiver,ast.Name):
                receiver_name = receiver.id
            elif isinstance(receiver,ast.Call) and isinstance(receiver.func,ast.Name):
                receiver_name = receiver.func.id + "()"
            else:
                receiver_name = "other_expression"
            call_sites.append({"method":name,"receiver":receiver_name,
                               "keyword_names":sorted(k.arg for k in node.keywords if k.arg)})
    if isinstance(node,ast.Assign) and isinstance(node.value,ast.Call):
        constructor = node.value.func.id if isinstance(node.value.func,ast.Name) else None
        if constructor:
            for target in node.targets:
                if isinstance(target,ast.Name) and target.id in ("brain", "planner", "runner", "worker"):
                    constructor_bindings.append({"variable":target.id,"constructor":constructor})

allowed = {"product_research", "product_validation"}
gateway_codes = set(build_factory_gateway().describe())
defined_planners = []
for path in sorted(root.glob("*.py"))[:300]:
    if not path.is_file() or path.is_symlink() or path.stat().st_size > 350000:
        continue
    data = path.read_bytes()
    if b"def plan_product_factory_step" in data or b"def decide_product_factory_step" in data:
        defined_planners.append(path.stem)

print("AGENT_FLEET_FACTORY_COMMAND_PREFLIGHT="+json.dumps({
    "schema":"saeit.agent.factory-command-preflight.v1", "read_only":True,
    "command_imports":imports[:20],
    "command_cli_options":sorted(set(arguments))[:30],
    "command_dispatch_calls":call_sites[:15],
    "command_constructor_bindings":constructor_bindings[:12],
    "factory_gateway_supports":sorted(allowed & gateway_codes),
    "factory_gateway_missing":sorted(allowed - gateway_codes),
    "planner_definition_module_names":defined_planners[:20],
    "autonomous_brain_has_product_factory_plan":hasattr(AutonomousBrain,"plan_product_factory_step"),
    "task_mutations":0,"commands_executed":0,
},sort_keys=True,separators=(",",":")))
PY

# Confirm factory-specific worker API compatibility against the installed
# runtime without claiming or completing any queued task.
"$python_bin" - <<'PY'
import hashlib
import inspect
import json
from pathlib import Path

import django
django.setup()
from core.worker_runner import WorkerRunner
from core.task_runtime import TaskRuntime
from core.tool_gateway import ToolGateway

def signature(obj, name):
    method = getattr(obj, name, None)
    if method is None:
        return {"exists":False}
    result = {"exists":True}
    try:
        result["parameter_names"] = list(inspect.signature(method).parameters)
    except (ValueError, TypeError):
        result["parameter_names"] = None
    return result

root = Path.home() / "factory-runtime/django-app/core"
filenames = ("worker_runner.py", "task_runtime.py", "tool_gateway.py",
             "factory_contracts.py", "autonomous_brain.py")
source_hashes = {}
for name in filenames:
    path = root / name
    if path.is_file() and not path.is_symlink() and path.stat().st_size < 350000:
        source_hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    else:
        source_hashes[name] = "unavailable_or_unsafe"

print("AGENT_FLEET_FACTORY_WORKER_COMPATIBILITY="+json.dumps({
    "schema":"saeit.agent.factory-worker-compatibility.v1", "read_only":True,
    "worker_init":signature(WorkerRunner,"__init__"),
    "worker_run":signature(WorkerRunner,"run"),
    "runtime_complete":signature(TaskRuntime,"complete"),
    "runtime_fail":signature(TaskRuntime,"fail"),
    "gateway_invoke":signature(ToolGateway,"invoke"),
    "gateway_authorize":signature(ToolGateway,"authorize"),
    "gateway_factory_adapter":signature(ToolGateway,"execute_factory_adapter"),
    "sha256_prefixes":source_hashes,
    "tasks_modified":0,"tasks_executed":0,
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

# Estimate which historical factory tasks could pass the existing non-writing
# identity/grant gates. This is a conservative preview, not an authorization
# token and never claims, resumes, or executes a task.
"$python_bin" - <<'PY'
import collections
import json

import django
django.setup()

from django.conf import settings
from django.utils import timezone
from core.models import AgentCapability, AgentTask, AgentToolGrant, FactoryRun

now = timezone.now()
owners = ("factory-market-research-agent", "factory-opportunity-validation-agent")
queued = AgentTask.objects.filter(status="queued", agent__code__in=owners).select_related(
    "agent", "factory_run", "product"
).order_by("pk")
counts = collections.Counter()
per_action = collections.Counter()
scopes = collections.Counter()
for task in queued.iterator(chunk_size=100):
    per_action[task.action_type] += 1
    reasons = []
    if not task.agent.active:
        reasons.append("inactive_agent")
    if task.action_type != task.capability_code or not task.action_type.startswith("product_"):
        reasons.append("capability_mismatch")
    if not AgentCapability.objects.filter(
        code=task.capability_code, active=True, agents__pk=task.agent_id
    ).exists():
        reasons.append("missing_active_capability")
    if task.attempt_count >= task.max_attempts:
        reasons.append("retry_exhausted")
    if task.next_retry_at and task.next_retry_at > now:
        reasons.append("retry_not_due")
    if not task.factory_run_id or task.factory_run.status != "active":
        reasons.append("missing_active_factory_run")
    elif task.factory_run.product_id != task.product_id:
        reasons.append("run_product_mismatch")
    if task.product_id is None:
        reasons.append("no_existing_product")
    if task.environment != str(getattr(settings, "FACTORY_ENVIRONMENT", "development")):
        reasons.append("environment_mismatch")
    resource = f"product:{task.product_id}" if task.product_id else "product:new"
    grants = AgentToolGrant.objects.filter(
        agent_id=task.agent_id, capability_code=task.capability_code,
        tool_code=task.action_type, environment=task.environment,
        active=True, revoked_at__isnull=True, valid_until__gt=now,
    ).values_list("resource_scope", flat=True)
    if not any(scope == resource or (
        scope.endswith(":*") and resource.startswith(scope[:-1])
    ) for scope in grants):
        reasons.append("no_valid_grant")
    if not isinstance(task.prerequisite_snapshot, dict) or not task.prerequisite_snapshot.get("digest"):
        reasons.append("missing_snapshot_digest")
    if not reasons:
        counts["passes_static_preflight_only"] += 1
    for reason in reasons:
        counts[reason] += 1
    scopes["has_product" if task.product_id else "no_product"] += 1

print("AGENT_FLEET_FACTORY_STATIC_READINESS=" + json.dumps({
    "schema":"saeit.agent.factory-static-readiness.v1", "read_only":True,
    "queued_total":sum(per_action.values()), "by_action":dict(sorted(per_action.items())),
    "preflight_flags":dict(sorted(counts.items())), "product_links":dict(sorted(scopes.items())),
    "active_factory_runs":FactoryRun.objects.filter(status="active").count(),
    "tasks_claimed":0,"tasks_executed":0,"tasks_modified":0,
},sort_keys=True,separators=(",",":")))
PY

# The one-product native line 41 uses a signed recipe slot on disk. Do not
# mistake 443 old Django FactoryRun(status="active") records for its slot.
# Count only exact, explicit recipe identity references in Django metadata;
# titles or free-text goals must never authorize a binding.
"$python_bin" - <<'PY'
import collections
import json
from pathlib import Path

import django
django.setup()

from core.models import AgentTask, FactoryRun

recipe = "farm_enterprise_economics"
slot = Path('/home/githubops/factory-runtime/private/autonomous-product-cycle/quality-excellence/product-flow/active-slots/current.json')
native = {"state": "unavailable", "active_count": None, "active_recipe_matches": False,
          "slot_schema_valid": False}
if slot.is_symlink():
    native["state"] = "unsafe_symlink"
elif slot.is_file() and slot.stat().st_size < 2000000:
    try:
        data = json.loads(slot.read_text(encoding="utf-8"))
        active = data.get("active") if isinstance(data, dict) else None
        valid = (data.get("schema") == "saeit.factory.product-slots.v1"
                 and isinstance(active, list)
                 and all(isinstance(item, dict) and isinstance(item.get("recipe"), str)
                         for item in active))
        native = {"state": "valid" if valid else "invalid_schema",
                  "active_count": len(active) if isinstance(active, list) else None,
                  "active_recipe_matches": bool(valid and len(active) == 1
                                                and active[0]["recipe"] == recipe),
                  "slot_schema_valid": bool(valid)}
    except (OSError, ValueError, UnicodeError):
        native["state"] = "unreadable"

def evidence_fields(meta):
    if not isinstance(meta, dict):
        return []
    fields = [key for key in ("recipe", "recipe_slug", "product_slug", "product_code", "sku")
              if meta.get(key) == recipe]
    for container in ("factory", "production", "source_recipe"):
        value = meta.get(container)
        if isinstance(value, dict):
            fields.extend(f"{container}.{key}" for key in ("recipe", "recipe_slug", "product_slug")
                          if value.get(key) == recipe)
        elif container == "source_recipe" and value == recipe:
            fields.append(container)
    return fields

counts = collections.Counter()
candidates = []
for task in AgentTask.objects.filter(
    status="queued", action_type="product_validation",
    agent__code="factory-opportunity-validation-agent"
).select_related("product", "factory_run").iterator(chunk_size=100):
    if not task.product_id or not task.factory_run_id:
        counts["missing_product_or_run"] += 1
        continue
    matches = evidence_fields(task.product.metadata)
    if not matches:
        counts["no_explicit_recipe_identity"] += 1
        continue
    for match in matches:
        counts["exact_identity."+match] += 1
    if (task.factory_run.status == "active"
            and task.factory_run.product_id == task.product_id):
        candidates.append((task.pk, task.product_id, task.factory_run.run_id))
    else:
        counts["identity_but_run_invalid"] += 1

unique_runs = sorted({row[2] for row in candidates})
binding_safe = bool(native["active_recipe_matches"] and len(unique_runs) == 1)
print("AGENT_FLEET_SINGLE_PRODUCT_RECONCILIATION="+json.dumps({
    "schema":"saeit.agent.native-django-factory-reconciliation.v1",
    "read_only":True,"native":native,
    "queued_validation_tasks_examined":sum(
        1 for _ in AgentTask.objects.filter(
            status="queued", action_type="product_validation",
            agent__code="factory-opportunity-validation-agent").values_list("pk", flat=True).iterator()),
    "identity_counts":dict(sorted(counts.items())),
    "matching_task_count":len(candidates),"matching_distinct_run_count":len(unique_runs),
    "single_run_identity_proven":binding_safe,
    "candidate_run_id":unique_runs[0] if binding_safe else None,
    "candidate_task_id":candidates[0][0] if binding_safe else None,
    "factory_run_records_marked_active":FactoryRun.objects.filter(status="active").count(),
    "run_bound":False,"tasks_executed":0,"db_writes":0,
},sort_keys=True,separators=(",",":")))
PY

# Never print crontab commands, inline environment values, or process arguments.
"$python_bin" - <<'PY'
import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
import stat

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
        "mojtrade_observer": "SAEIT_MOJTRADE_OBSERVER_V1" in command,
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

# A cron-launched observer normally runs for seconds, so process counts alone
# cannot prove that it is absent or healthy. Check its private receipt, source,
# scheduled entry and unexpired payload without emitting market or wallet data.
operations = Path.home() / "factory-runtime/operations/mojtrade"
private = Path.home() / "factory-runtime/private/mojtrade"
tagged = sum(bool(entry["route_flags"]["mojtrade_observer"]) for entry in entries)
scheduled_hourly = any(
    entry["route_flags"]["mojtrade_observer"] and entry["schedule"] == "13 * * * *"
    for entry in entries
)

def private_file(path, limit=96000):
    try:
        if path.is_symlink() or not path.is_file():
            return None
        metadata = path.stat()
        if stat.S_IMODE(metadata.st_mode) & 0o077 or not 0 < metadata.st_size <= limit:
            return None
        return path.read_bytes()
    except OSError:
        return None

def timestamp(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(timezone.utc) if parsed.tzinfo else None

try:
    safe_private = (private.is_dir() and not private.is_symlink()
                    and stat.S_IMODE(private.stat().st_mode) == 0o700)
except OSError:
    safe_private = False
source = (private_file(operations / "observer.py", limit=200000)
          if operations.is_dir() and not operations.is_symlink() else None)
receipt = payload = None
if safe_private:
    try:
        receipt_bytes = private_file(private / "activation-receipt.json")
        payload_bytes = private_file(private / "validated-payload.json")
        receipt = json.loads(receipt_bytes) if receipt_bytes else None
        payload = json.loads(payload_bytes) if payload_bytes else None
    except (OSError, UnicodeError, ValueError, TypeError):
        pass

source_matches = bool(
    isinstance(receipt, dict) and source is not None
    and receipt.get("schema") == "mojtrade.vps-observer-activation-receipt.v1"
    and receipt.get("source_sha256") == hashlib.sha256(source).hexdigest()
    and receipt.get("execution") == "disabled"
    and receipt.get("orders") == 0
    and receipt.get("publication_enabled") is False
)
now = datetime.now(timezone.utc)
generated = timestamp(payload.get("generated_at")) if isinstance(payload, dict) else None
expires = timestamp(payload.get("expires_at")) if isinstance(payload, dict) else None
signals = payload.get("signals") if isinstance(payload, dict) else None
payload_fresh = bool(
    generated and expires and generated <= now <= expires
    and isinstance(signals, list) and len(signals) == 2
    and [signal.get("symbol") for signal in signals if isinstance(signal, dict)]
        == ["BTC/USD", "ETH/USD"]
    and payload.get("schema_version") == 1
    and payload.get("source") == "mojtrade-vps"
)
print("AGENT_FLEET_MOJTRADE_RUNTIME=" + json.dumps({
    "read_only": True,
    "cron_entries": tagged,
    "hourly_schedule_valid": scheduled_hourly,
    "private_directory_secure": safe_private,
    "source_matches_receipt": source_matches,
    "payload_fresh": payload_fresh,
    "observer_operational_evidence": (
        tagged == 1 and scheduled_hourly and source_matches and payload_fresh
    ),
    "orders_executed_by_audit": 0,
    "real_trading_supported_by_observer": False,
}, sort_keys=True, separators=(",", ":")))
PY
echo AGENT_FLEET_AUDIT_READ_ONLY_COMPLETE
