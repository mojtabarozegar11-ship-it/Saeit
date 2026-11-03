"""Contract and isolated database checks for the production allowlisted relay worker.

No live server, purchase, factory process or payment is exercised by these tests.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sqlite3
from types import SimpleNamespace

import pytest

WORKER_PATH = Path(__file__).resolve().parents[1] / "scripts" / "zomorod_allowlisted_policy_worker.py"
WORKFLOW_PATH = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "zomorod-private-command-dispatch.yml"


@pytest.fixture
def worker(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("zmr_allowlisted_policy_worker", WORKER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "PRIVATE", tmp_path)
    monkeypatch.setattr(module, "DB", tmp_path / "command-center.sqlite3")
    monkeypatch.setattr(module, "POLICY_FILE", tmp_path / "factory-single-product-policy-v1.json")
    monkeypatch.setattr(module.pwd, "getpwuid", lambda uid: SimpleNamespace(pw_name="zomorod2"))
    with sqlite3.connect(module.DB) as db:
        db.executescript("""
        CREATE TABLE tasks (
            id INTEGER PRIMARY KEY, request_key TEXT, actor_id INTEGER,
            title TEXT, detail TEXT
        );
        CREATE TABLE task_quality (task_id INTEGER PRIMARY KEY);
        CREATE TABLE task_events (
            id INTEGER PRIMARY KEY, task_id INTEGER, actor_id INTEGER,
            kind TEXT, note TEXT
        );
        CREATE TABLE bridge_receipts (
            id TEXT PRIMARY KEY, task_id INTEGER, accepted_at INTEGER
        );
        """)
    return module


def insert_signed_task(worker, key="0123456789abcdef0123456789abcdef", *,
                       title=None, detail=None):
    import time
    with sqlite3.connect(worker.DB) as db:
        cursor = db.execute(
            "INSERT INTO tasks(request_key, actor_id, title, detail) VALUES (?, 0, ?, ?)",
            (key, title or worker.TITLE, detail or worker.DETAIL),
        )
        task_id = cursor.lastrowid
        db.execute("INSERT INTO task_quality(task_id) VALUES (?)", (task_id,))
        db.execute(
            "INSERT INTO task_events(task_id, actor_id, kind, note) VALUES (?, 0, ?, ?)",
            (task_id, "bridge_signed_task", "Authenticated; not executed"),
        )
        db.execute(
            "INSERT INTO bridge_receipts(id, task_id, accepted_at) VALUES (?, ?, ?)",
            (key, task_id, int(time.time())),
        )
    return key, task_id


def test_exact_signed_task_applies_durable_policy_and_readback(worker, capsys):
    key, task_id = insert_signed_task(worker)
    worker.apply()
    assert "POLICY_APPLIED=YES" in capsys.readouterr().out
    assert worker.POLICY_FILE.read_bytes() == worker.DATA
    assert worker.POLICY_FILE.stat().st_mode & 0o077 == 0
    worker.verify(key)
    assert "PRIVATE_EXECUTION_RECEIPT=VERIFIED" in capsys.readouterr().out
    with sqlite3.connect(worker.DB) as db:
        assert db.execute(
            "SELECT COUNT(*) FROM bridge_execution_receipts WHERE task_id=?", (task_id,)
        ).fetchone()[0] == 1
        assert db.execute(
            "SELECT COUNT(*) FROM task_events WHERE task_id=? AND kind=?",
            (task_id, worker.EVENT_KIND),
        ).fetchone()[0] == 1
    worker.apply()
    assert "POLICY_APPLIED=NOT_APPLICABLE" in capsys.readouterr().out


def test_other_authenticated_task_remains_queued_without_execution(worker, capsys):
    insert_signed_task(worker, title="Other legitimate task")
    worker.apply()
    assert "POLICY_APPLIED=NOT_APPLICABLE" in capsys.readouterr().out
    assert not worker.POLICY_FILE.exists()


def test_ambiguous_recent_allowed_tasks_are_rejected_without_writes(worker):
    insert_signed_task(worker)
    insert_signed_task(worker, key="fedcba9876543210fedcba9876543210")
    with pytest.raises(RuntimeError, match="AMBIGUOUS_ALLOWLISTED_TASK"):
        worker.apply()
    assert not worker.POLICY_FILE.exists()


def test_conflicting_existing_policy_is_never_overwritten(worker):
    insert_signed_task(worker)
    worker.POLICY_FILE.write_text("conflicting owner's policy", encoding="utf-8")
    worker.POLICY_FILE.chmod(0o600)
    with pytest.raises(RuntimeError, match="POLICY_CONFLICT_REJECTED"):
        worker.apply()
    assert worker.POLICY_FILE.read_text(encoding="utf-8") == "conflicting owner's policy"
    with sqlite3.connect(worker.DB) as db:
        assert db.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='bridge_execution_receipts'"
        ).fetchone()[0] == 0


def test_workflow_invokes_remote_worker_without_general_shell_dispatch():
    source = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert "- name: Apply allowlisted factory policy and independently verify private receipt" in source
    assert 'if: steps.gate.outputs.operation == \'accept\'' in source
    assert "'python3 -B - apply' < scripts/zomorod_allowlisted_policy_worker.py" in source
    assert 'verify \'$command_id\'' in source
    assert '[[ "$command_id" =~ ^[0-9a-f]{32}$ ]]' in source
    assert 'grep -Fxq "PRIVATE_EXECUTION_RECEIPT=VERIFIED"' in source
    assert 'echo "COMPANY_WORK_EXECUTION=ALLOWLISTED_POLICY_APPLIED"' in source
    assert 'echo "COMPANY_WORK_EXECUTION=NOT_PERFORMED"' in source
    assert "shell=True" not in WORKER_PATH.read_text(encoding="utf-8")
    assert "subprocess" not in WORKER_PATH.read_text(encoding="utf-8")
