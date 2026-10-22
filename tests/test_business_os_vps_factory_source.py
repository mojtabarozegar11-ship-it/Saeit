"""Offline contracts for the private factory management observer."""

import importlib.util
from pathlib import Path
import sqlite3
import sys


ROOT = Path(__file__).resolve().parent.parent


def _import(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_factory_source_does_not_invent_missing_tables():
    observer = _import(ROOT / "scripts/business_os_vps_private_factory_metrics.py", "test_vps_factory_observer")
    analysis = _import(ROOT / "core/business_management.py", "test_vps_factory_review")
    with sqlite3.connect(":memory:") as connection:
        metric = observer._count_or_unknown(
            connection, analysis, "2026-10-22T00:00:00Z", "core_agenttask",
            "WHERE status='queued'", ("status",)
        )
    assert metric["state"] == "unknown"
    assert metric["value"] is None


def test_factory_source_preserves_zero_when_source_exists():
    observer = _import(ROOT / "scripts/business_os_vps_private_factory_metrics.py", "test_vps_factory_observer_2")
    analysis = _import(ROOT / "core/business_management.py", "test_vps_factory_review_2")
    with sqlite3.connect(":memory:") as connection:
        connection.execute("CREATE TABLE core_agenttask (id INTEGER PRIMARY KEY, status TEXT)")
        metric = observer._count_or_unknown(
            connection, analysis, "2026-10-22T00:00:00Z", "core_agenttask",
            "WHERE status='blocked'", ("status",)
        )
    assert metric["state"] == "observed"
    assert metric["value"] == 0
    assert metric["source"] == "vps_private_factory_sqlite:core_agenttask"


def test_factory_source_reads_queued_and_blocked_independently():
    observer = _import(ROOT / "scripts/business_os_vps_private_factory_metrics.py", "test_vps_factory_observer_3")
    analysis = _import(ROOT / "core/business_management.py", "test_vps_factory_review_3")
    with sqlite3.connect(":memory:") as connection:
        connection.execute("CREATE TABLE core_agenttask (id INTEGER PRIMARY KEY, status TEXT)")
        connection.executemany("INSERT INTO core_agenttask(status) VALUES (?)", [("queued",), ("queued",), ("blocked",)])
        connection.execute("PRAGMA query_only=ON")
        queued = observer._count_or_unknown(connection, analysis, "2026-10-22T00:00:00Z", "core_agenttask", "WHERE status='queued'", ("status",))
        blocked = observer._count_or_unknown(connection, analysis, "2026-10-22T00:00:00Z", "core_agenttask", "WHERE status='blocked'", ("status",))
    assert queued["value"] == 2
    assert blocked["value"] == 1
