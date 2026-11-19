import importlib.util
from pathlib import Path
import sqlite3
import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("census", ROOT / "deploy/mojtaba_django_census_readonly.py")
C = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(C)


def fixture_db(path):
    with sqlite3.connect(path) as db:
        db.executescript("""
          CREATE TABLE core_agent (id INTEGER PRIMARY KEY, code TEXT, active INTEGER);
          CREATE TABLE core_agenttask (id INTEGER PRIMARY KEY, agent_id INTEGER, status TEXT,
            action_type TEXT DEFAULT '', capability_code TEXT DEFAULT '', risk_snapshot TEXT DEFAULT 'low',
            execution_id TEXT DEFAULT '', attempt_count INTEGER DEFAULT 0, max_attempts INTEGER DEFAULT 3);
          CREATE TABLE core_approvalrequest (target_id TEXT, target_type TEXT, status TEXT);
          INSERT INTO core_agent VALUES (1,'mojtaba-bot-ai',1),(2,'private-identity',0);
          INSERT INTO core_agenttask (id,agent_id,status) VALUES (1,1,'completed'),(2,2,'queued'),(3,2,'private-status'),(4,7,'running');
        """)


def test_registry_census_counts_dependencies_and_redacts_unknown_values(tmp_path):
    path = tmp_path / "database.sqlite3"
    fixture_db(path)
    before = path.read_bytes()
    r = C.sqlite_census(str(path), tmp_path)
    assert r["registry_records"] == 2
    assert r["enabled_registry_records"] == 1
    assert r["nonterminal_tasks"] == 2
    assert r["orphan_task_records"] == 1
    assert "private-identity" not in str(r) and "private-status" not in str(r)
    assert path.read_bytes() == before


def test_sqlite_refuses_sidecar_and_missing_file(tmp_path):
    path = tmp_path / "database.sqlite3"
    fixture_db(path)
    Path(str(path)+"-wal").touch()
    with pytest.raises(ValueError):
        C.sqlite_census(str(path), tmp_path)
    missing = tmp_path / "absent.sqlite3"
    with pytest.raises(ValueError):
        C.sqlite_census(str(missing), tmp_path)
    assert not missing.exists()


def test_workflow_is_manual_main_only_and_source_is_read_only():
    text = (ROOT / ".github/workflows/mojtaba-django-census-readonly.yml").read_text()
    events = text.split("on:", 1)[1].split("permissions:",1)[0]
    assert "workflow_dispatch:" in events and "push:" not in events and "schedule:" not in events
    assert "github.ref == 'refs/heads/main'" in text
    assert "StrictHostKeyChecking=yes" in text
    assert "runs-on: [self-hosted, factory-vps]" in text
    assert all(q.startswith("SELECT ") for q in C.QUERIES)


def run_summary(tmp_path, roles, inconsistent=False):
    import json
    import subprocess
    import sys
    import textwrap
    workflow = (ROOT / ".github/workflows/mojtaba-django-census-readonly.yml").read_text()
    source = textwrap.dedent(workflow.split("<<'SUMMARY'\n", 1)[1].split("\n          SUMMARY", 1)[0])
    for role in roles:
        result = {"schema": C.SCHEMA, "host": role, "state": "registry_snapshot_only",
                  "read_only_database_transaction": True, "retirement_authorized": False,
                  "registry_records": 1, "enabled_registry_records": 1,
                  "nonterminal_tasks": 1, "orphan_task_records": 0,
                  "agents": [{"code": "mojtaba-bot-ai", "enabled_registry_record": True,
                              "tasks": {"queued": 1}, "nonterminal_tasks": 0 if inconsistent else 1,
                              "pending_groups": [{"status":"queued", "action":"empty", "capability":"empty", "risk":"low",
                                **{k: int(k in ("total","without_approval_record")) for k in C.GROUP_COUNTS}}]}]}
        (tmp_path / (role + ".out")).write_text("MOJTABA_DJANGO_CENSUS=" + json.dumps(result) + "\n")
    return subprocess.run([sys.executable, "-c", source, str(tmp_path)],
                          cwd=ROOT, capture_output=True, text=True)


@pytest.mark.parametrize("roles", [(), ("vps",), ("cpanel",)])
def test_incomplete_host_summary_fails_closed(tmp_path, roles):
    r = run_summary(tmp_path, roles)
    assert r.returncode == 1
    assert "MOJTABA_DB_CENSUS_GATE=BLOCKED_INCOMPLETE" in r.stdout
    assert "PASS_REGISTRY_ONLY" not in r.stdout


def test_consistent_dual_host_summary_only_certifies_registry(tmp_path):
    r = run_summary(tmp_path, ("vps", "cpanel"))
    assert r.returncode == 0, r.stderr
    assert "MOJTABA_DB_CENSUS_VALID_HOSTS=2" in r.stdout
    assert "MOJTABA_DB_CENSUS_GATE=PASS_REGISTRY_ONLY" in r.stdout
    assert '"retirement_authorized": false' in r.stdout


def test_inconsistent_pending_counts_fail_closed(tmp_path):
    r = run_summary(tmp_path, ("vps", "cpanel"), inconsistent=True)
    assert r.returncode == 1
    assert "MOJTABA_DB_CENSUS_VALID_HOSTS=0" in r.stdout


def test_census_transport_diagnostics_are_redacted_and_pin_preserved():
    text = (ROOT / ".github/workflows/mojtaba-django-census-readonly.yml").read_text()
    assert "report_ssh_status vps_loopback" in text
    assert "ssh_connection_or_auth_failed" in text
    assert "host_fingerprint_mismatch_stop" in text
    assert "keyscan_unavailable" in text
    assert "&& -d /home/githubops/factory-runtime" not in text
    assert "StrictHostKeyChecking=yes" in text
    assert "ForwardAgent=no" in text
    assert not any(line.strip().startswith("cat ") and ".err" in line for line in text.splitlines())


def test_pending_detail_reconciles_and_redacts(tmp_path):
    path = tmp_path / "database.sqlite3"
    fixture_db(path)
    with sqlite3.connect(path) as db:
        db.execute("UPDATE core_agenttask SET action_type='private-action', capability_code='product_validation', execution_id='private-execution', attempt_count=3 WHERE id=2")
        db.execute("INSERT INTO core_approvalrequest VALUES ('2','AgentTask','pending'), ('2','AgentTask','approved'), ('2','AgentTask','pending')")
    before = path.read_bytes()
    result = C.sqlite_census(str(path), tmp_path)
    g = next(g for a in result["agents"] for g in a["pending_groups"] if g["status"] == "queued")
    assert g["action"].startswith("unknown:")
    assert g["capability"] == "product_validation"
    assert g["has_pending_approval"] == g["has_approved_record"] == 1
    assert g["with_execution_id"] == g["previously_attempted"] == g["attempt_limit_reached"] == 1
    assert g["without_approval_record"] == 0
    assert "private-action" not in str(result) and "private-execution" not in str(result)
    assert path.read_bytes() == before


def test_pending_detail_rejects_inconsistent_or_unsafe_group():
    g = {"status":"queued","action":"empty","capability":"empty","risk":"low",
         **{k: int(k in ("total","without_approval_record")) for k in C.GROUP_COUNTS}}
    row = {"tasks":{"queued":1}, "pending_groups":[g]}
    assert C.validate_pending_groups(row) == [g]
    for patch in ({"total":2}, {"action":"private-string"}, {"has_pending_approval":1}, {"total":True}):
        with pytest.raises(ValueError):
            C.validate_pending_groups({"tasks":{"queued":1}, "pending_groups":[{**g,**patch}]})
    with pytest.raises(ValueError):
        C.validate_pending_groups({"tasks":{"queued":2}, "pending_groups":[g,g]})
