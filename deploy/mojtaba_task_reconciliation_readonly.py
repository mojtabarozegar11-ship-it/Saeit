"""Minimal registry/task census. No app startup, task execution or raw payload output."""
import argparse
from collections import Counter
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import sqlite3
import sys

KNOWN = frozenset(("mojtaba-bot-ai", "economic-master-agent", "moj_1ro_1",
    "core_research", "newsletter-specialist", "newsletter-company-news",
    "newsletter-world-watch", "newsletter-unit-reports", "company-activity-intelligence",
    "content-director", "knowledge-content-director", "content-research",
    "factory-market-research-agent", "factory-opportunity-validation-agent"))
TERMINAL = frozenset(("completed", "failed", "cancelled"))
STATUS = TERMINAL | {"queued", "running", "blocked"}
ROLES = {"vps": ("githubops", "factory-runtime/django-app"),
         "cpanel": ("zomorod2", "Saeit")}
SCHEMA = "mojtaba.bot.ai.django-census.v2"
SAFE_CODES = frozenset(("product_research", "product_validation", "knowledge_content_generation",
    "research-write-review", "factory_native_review", "factory_f41_private_build"))
RISKS = frozenset(("low", "medium", "high", "critical"))
QUERIES = (
    "SELECT id, code, active FROM core_agent ORDER BY id LIMIT 10001",
    "SELECT agent_id, status, COUNT(*) FROM core_agenttask GROUP BY agent_id, status LIMIT 100001",
    "SELECT id, agent_id, status, action_type, capability_code, risk_snapshot, CASE WHEN execution_id <> '' THEN 1 ELSE 0 END, attempt_count, max_attempts FROM core_agenttask WHERE status NOT IN ('completed', 'failed', 'cancelled') LIMIT 100001",
    "SELECT target_id, status FROM core_approvalrequest WHERE target_type = 'AgentTask' LIMIT 100001",
)


def safe_code(value):
    if value in SAFE_CODES:
        return value
    if value == "":
        return "empty"
    return "unknown:" + hashlib.sha256(str(value).encode()).hexdigest()[:16]


def valid_code(value):
    return isinstance(value, str) and (value in SAFE_CODES or value == "empty"
        or re.fullmatch(r"unknown:[0-9a-f]{16}", value) is not None)


def pending_details(cursor, rows):
    cursor.execute(QUERIES[2])
    pending = cursor.fetchall()
    if len(pending) > 100000:
        raise ValueError("pending_bound")
    cursor.execute(QUERIES[3])
    approvals = cursor.fetchall()
    if len(approvals) > 100000:
        raise ValueError("approval_bound")
    by_task = {}
    for target_id, status in approvals:
        by_task.setdefault(str(target_id), set()).add(
            status if status in ("pending", "approved") else "other")
    groups = {}
    for pk, agent_id, status, action, capability, risk, execution, attempts, maximum in pending:
        if agent_id not in rows:
            continue
        if type(attempts) is not int or type(maximum) is not int or min(attempts, maximum) < 0:
            raise ValueError("invalid_attempt_counts")
        k = (agent_id, status if status in STATUS else "unknown_nonterminal",
             safe_code(action), safe_code(capability), risk if risk in RISKS else "unknown")
        g = groups.setdefault(k, Counter())
        g["total"] += 1
        g["with_execution_id"] += bool(execution)
        g["previously_attempted"] += attempts > 0
        g["attempt_limit_reached"] += attempts >= maximum
        approval_states = by_task.get(str(pk), set())
        g["has_pending_approval"] += "pending" in approval_states
        g["has_approved_record"] += "approved" in approval_states
        g["has_other_approval"] += "other" in approval_states
        g["without_approval_record"] += not approval_states
    for row in rows.values():
        row["pending_groups"] = []
    for (agent_id, status, action, capability, risk), counts in sorted(groups.items()):
        rows[agent_id]["pending_groups"].append({
            "status": status, "action": action, "capability": capability,
            "risk": risk, **dict(counts)})
    for row in rows.values():
        validate_pending_groups(row)


GROUP_COUNTS = ("total", "with_execution_id", "previously_attempted",
    "attempt_limit_reached", "has_pending_approval", "has_approved_record",
    "has_other_approval", "without_approval_record")


def validate_pending_groups(row):
    """Validate exact per-status reconciliation and output vocabulary."""
    counts = Counter()
    seen = set()
    for g in row["pending_groups"]:
        if set(g) != {"status", "action", "capability", "risk", *GROUP_COUNTS}:
            raise ValueError("group_shape")
        if (g["status"] not in (STATUS - TERMINAL) | {"unknown_nonterminal"}
                or not valid_code(g["action"]) or not valid_code(g["capability"])
                or g["risk"] not in RISKS | {"unknown"}):
            raise ValueError("group_label")
        key = tuple(g[k] for k in ("status", "action", "capability", "risk"))
        if key in seen:
            raise ValueError("duplicate_group")
        seen.add(key)
        if (any(type(g[k]) is not int or g[k] < 0 for k in GROUP_COUNTS)
                or g["total"] <= 0 or any(g[k] > g["total"] for k in GROUP_COUNTS)):
            raise ValueError("group_count")
        if any(g[k] + g["without_approval_record"] > g["total"]
               for k in ("has_pending_approval", "has_approved_record", "has_other_approval")):
            raise ValueError("approval_counts")
        counts[g["status"]] += g["total"]
    if dict(counts) != {k: v for k, v in row["tasks"].items() if k not in TERMINAL and v}:
        raise ValueError("group_status_reconciliation")
    return row["pending_groups"]


def collect(cursor):
    cursor.execute(QUERIES[0])
    agents = cursor.fetchall()
    if len(agents) > 10000:
        raise ValueError("registry_bound")
    rows = {}
    for pk, code, active in agents:
        if type(active) not in (bool, int) or active not in (0, 1):
            raise ValueError("invalid_active")
        label = code if code in KNOWN else "unknown:" + hashlib.sha256(str(code).encode()).hexdigest()[:16]
        rows[pk] = {"code": label, "enabled_registry_record": bool(active), "tasks": {}}
    cursor.execute(QUERIES[1])
    groups = cursor.fetchall()
    if len(groups) > 100000:
        raise ValueError("task_group_bound")
    orphans = 0
    for pk, status, count in groups:
        if type(count) is not int or count < 0:
            raise ValueError("invalid_count")
        if pk not in rows:
            orphans += count
            continue
        counts = rows[pk]["tasks"]
        name = status if status in STATUS else "unknown_nonterminal"
        counts[name] = counts.get(name, 0) + count
    for row in rows.values():
        row["nonterminal_tasks"] = sum(n for k, n in row["tasks"].items() if k not in TERMINAL)
    pending_details(cursor, rows)
    values = list(rows.values())
    return {"registry_records": len(values),
            "enabled_registry_records": sum(r["enabled_registry_record"] for r in values),
            "nonterminal_tasks": sum(r["nonterminal_tasks"] for r in values),
            "orphan_task_records": orphans, "agents": values}


def sqlite_census(name, app):
    path = Path(name)
    if not path.is_absolute():
        raise ValueError("relative_db_name")
    if (not path.is_file() or path.is_symlink()
            or not path.resolve().is_relative_to(app.resolve())
            or any(Path(str(path) + suffix).exists() for suffix in ("-wal", "-journal", "-shm"))):
        raise ValueError("sqlite_snapshot_unavailable")
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro&immutable=1", uri=True, timeout=5)) as db:
        db.execute("PRAGMA query_only=ON")
        result = collect(db.cursor())
    # Do not certify an immutable snapshot if a writer's sidecar appeared.
    if any(Path(str(path) + suffix).exists() for suffix in ("-wal", "-journal", "-shm")):
        raise ValueError("sqlite_snapshot_changed")
    return result


def server_census(connection):
    if connection.vendor not in ("mysql", "postgresql"):
        raise ValueError("unsupported_backend")
    try:
        connection.ensure_connection()
        if not connection.get_autocommit():
            raise ValueError("unexpected_transaction")
        with connection.cursor() as cursor:
            if connection.vendor == "mysql":
                cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
                cursor.execute("START TRANSACTION")
            else:
                cursor.execute("BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY")
            try:
                return collect(cursor, table_names=lambda: connection.introspection.table_names(cursor))
            finally:
                cursor.execute("ROLLBACK")
    finally:
        connection.close()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--role", choices=ROLES, required=True)
    role = p.parse_args().role
    user, relative = ROLES[role]
    base = {"schema": SCHEMA, "host": role, "state": "unknown",
            "verified_live_agents": None, "retirement_authorized": False,
            "registry_records": None, "enabled_registry_records": None,
            "nonterminal_tasks": None, "agents": []}
    try:
        if pwd.getpwuid(os.geteuid()).pw_name != user:
            raise ValueError("wrong_user")
        app = Path(pwd.getpwuid(os.geteuid()).pw_dir) / relative
        if Path.cwd().resolve() != app.resolve() or not (app / "manage.py").is_file():
            raise ValueError("wrong_app")
        sys.path.insert(0, str(app))
        os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
        from django.db import connections
        connection = connections["default"]
        if connection.vendor == "sqlite":
            data = sqlite_census(connection.settings_dict["NAME"], app)
        else:
            data = server_census(connection)
        base.update(data, state="registry_snapshot_only",
                    backend=connection.vendor, read_only_database_transaction=True)
    except Exception:
        # Never output exception text, SQL credentials, connection URLs or payloads.
        base["state"] = "database_or_schema_unavailable"
    print("MOJTABA_DJANGO_CENSUS=" + json.dumps(base, sort_keys=True))


# V3 extension: a redacted snapshot of evidence, not an execution policy.
# The existing pinned-host and database read-only entrypoint is retained.
SCHEMA = "mojtaba.bot.ai.task-reconciliation.v3"
_census_collect = collect
FACTORY_ACTIONS = frozenset(("product_research", "product_validation"))
REASON_RULES = (
    ("owner_provenance", r"owner.{0,40}provenance|provenance.{0,40}owner"),
    ("approval_or_permission", r"approval|permission|unauthoriz"),
    ("budget_or_capacity", r"budget|capacity|quota|insufficient funds"),
    ("retry_or_timeout", r"retry|timeout|backoff|exhausted"),
    ("run_or_product_binding", r"factoryrun|factory.run|product.{0,40}(missing|mismatch|binding)|single.active"),
    ("research_or_evidence", r"evidence|citation|research.source"),
    ("configuration", r"configuration|credential|provider|api.key"),
)

def reason_tags(value):
    if isinstance(value, (str, bytes)):
        try:
            value = json.loads(value)
        except (TypeError, ValueError, UnicodeError):
            return ("unstructured_reason",)
    if not isinstance(value, dict):
        return ("unstructured_reason",)
    msg = " ".join(v[:3000] for k in ("error", "reason", "message", "error_code")
                   if isinstance((v := value.get(k)), str)).lower()
    if not msg.strip():
        return ("unrecorded_reason",)
    return tuple(label for label, pattern in REASON_RULES if re.search(pattern, msg)) or ("other_reason",)

def task_reconciliation(cursor, *, table_names=None):
    cursor.execute("SELECT * FROM core_agenttask WHERE 1=0")
    columns = {c[0].lower() for c in cursor.description}
    optional = ("project_id", "product_id", "factory_run_id")
    required = {"id", "status", "action_type", "attempt_count", "max_attempts", "output_data"}
    if not required.issubset(columns):
        raise ValueError("task_reconciliation_schema")
    present = [c for c in optional if c in columns]
    # Only hard-coded column names can enter SQL; raw values never leave this function.
    select = "id,status,action_type,attempt_count,max_attempts,output_data"
    if present:
        select += "," + ",".join(present)
    cursor.execute("SELECT " + select + " FROM core_agenttask "
                   "WHERE status NOT IN ('completed','failed','cancelled') ORDER BY id LIMIT 100001")
    rows = cursor.fetchall()
    if len(rows) > 100000:
        raise ValueError("reconciliation_bound")
    groups = Counter()
    reasons = Counter()
    link_counts = Counter()
    exhausted = Counter()
    exhausted_cases = []
    candidate_keys = Counter()
    run_ids = set()
    for pk, status, action, attempts, maximum, output, *links in rows:
        action = safe_code(action)
        status = status if status in STATUS else "unknown_nonterminal"
        if type(attempts) is not int or type(maximum) is not int or min(attempts, maximum) < 0:
            raise ValueError("reconciliation_attempts")
        groups[(action, status)] += 1
        link = dict(zip(present, links))
        for col in optional:
            state = "field_absent" if col not in link else "null" if link[col] is None else "present"
            link_counts[(action, status, col, state)] += 1
        if status == "blocked":
            for tag in reason_tags(output):
                reasons[(action, tag)] += 1
        if attempts >= maximum:
            tags = reason_tags(output)
            exhausted[(action, status, tags)] += 1
            if len(exhausted_cases) >= 1000:
                raise ValueError("exhausted_case_bound")
            exhausted_cases.append({
                "case": len(exhausted_cases) + 1, "action": action, "status": status,
                "attempts": attempts, "maximum": maximum, "reason_tags": list(tags),
                "links": {col: "field_absent" if col not in link else
                          "null" if link[col] is None else "present" for col in optional},
                "run_link_state": "not_evaluated",
                "_product": link.get("product_id"), "_run": link.get("factory_run_id"),
            })
        if action in FACTORY_ACTIONS and all(link.get(k) is not None for k in ("product_id", "factory_run_id")):
            candidate_keys[(action, link["product_id"], link["factory_run_id"])] += 1
            run_ids.add(link["factory_run_id"])
    def as_rows(counter, keys):
        return [dict(zip(keys, k), total=n) for k,n in sorted(counter.items(), key=lambda x: str(x[0]))]
    runs = {"state": "field_absent_or_no_linked_tasks"}
    if run_ids:
        if table_names is None:
            if not isinstance(cursor, sqlite3.Cursor):
                raise ValueError("run_table_metadata_unavailable")
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            names = {row[0] for row in cursor.fetchall()}
        else:
            names = set(table_names())
    else:
        names = set()
    if run_ids and "core_factoryrun" not in names:
        runs = {"state": "run_schema_incomplete"}
    elif run_ids:
        # Read only the status/product association for runs; no raw IDs exported.
        cursor.execute("SELECT * FROM core_factoryrun WHERE 1=0")
        run_cols = {c[0].lower() for c in cursor.description}
        if {"id", "status", "product_id"}.issubset(run_cols):
            cursor.execute("SELECT id,status,product_id FROM core_factoryrun LIMIT 100001")
            run_rows = cursor.fetchall()
            if len(run_rows) > 100000:
                raise ValueError("run_reconciliation_bound")
            by_id = {pk:(status, product) for pk,status,product in run_rows if pk in run_ids}
            result = Counter()
            for (action, product, run), n in candidate_keys.items():
                entry = by_id.get(run)
                outcome = ("run_missing" if entry is None else
                           "run_product_mismatch" if entry[1] != product else
                           "run_active_product_match" if entry[0] == "active" else
                           "run_not_active")
                result[(action, outcome)] += n
            runs = {"state": "observed", "groups": as_rows(result, ("action","link_state"))}
            for case in exhausted_cases:
                if case["action"] in FACTORY_ACTIONS and case["_product"] is not None and case["_run"] is not None:
                    entry = by_id.get(case["_run"])
                    case["run_link_state"] = ("run_missing" if entry is None else
                        "run_product_mismatch" if entry[1] != case["_product"] else
                        "run_active_product_match" if entry[0] == "active" else "run_not_active")
        else:
            runs = {"state": "run_schema_incomplete"}
    for case in exhausted_cases:
        del case["_product"], case["_run"]
    return {
        "pending": len(rows),
        "groups": as_rows(groups, ("action","status")),
        "blocked_reason_indicators_nonexclusive": as_rows(reasons, ("action","reason_tag")),
        "links": as_rows(link_counts, ("action","status","field","state")),
        "exhausted_groups": as_rows(exhausted, ("action","status","reason_tags")),
        "exhausted_cases_snapshot_local": exhausted_cases,
        "run_links": runs,
        "same_action_product_run_candidate_groups": sum(n > 1 for n in candidate_keys.values()),
        "same_action_product_run_candidate_tasks": sum(n for n in candidate_keys.values() if n > 1),
        "duplicates_proven": False,
        "execution_authorized": False,
        "cause_proven_by_keyword": False,
    }

def collect(cursor, *, table_names=None):
    result = _census_collect(cursor)
    evidence = task_reconciliation(cursor, table_names=table_names)
    if evidence["pending"] != result["nonterminal_tasks"]:
        raise ValueError("reconciliation_count_mismatch_or_orphans")
    result["task_reconciliation"] = evidence
    return result

if __name__ == "__main__":
    main()
