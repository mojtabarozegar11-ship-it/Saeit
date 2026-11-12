"""Offline regressions for the non-mutating two-host canonical topology observer."""
from __future__ import annotations

import importlib.util
import json
import hashlib
import sqlite3
from pathlib import Path
import tempfile
from unittest.mock import patch

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "deploy" / "mojtaba_live_topology_readonly.py"
spec = importlib.util.spec_from_file_location("mojtaba_live_topology_readonly", SCRIPT)
assert spec and spec.loader
observer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(observer)


def test_valid_routes_are_explicit_and_not_generic_aliases():
    assert observer.route_flags("python manage.py knowledge_agent_cycle") == [
        "knowledge_agent_cycle"
    ]
    assert observer.route_flags("python agent.py") == []
    assert observer.route_flags("python unrelated factory script") == []


def test_crontab_commands_are_hashed_without_leaking_secret_values():
    secret = "SECRET_INLINE_VALUE_01234"
    lines = (
        "13 * * * * /usr/bin/python manage.py knowledge_agent_cycle "
        f"API_TOKEN={secret}\n"
        "* * * * * /usr/bin/curl https://user:password@example.org/secret\n"
        "MALFORMED LINE\n"
    )
    rows = observer.safe_cron(lines)
    assert len(rows) == 2
    rendered = json.dumps(rows)
    assert secret not in rendered
    assert "password" not in rendered
    assert "example.org" not in rendered
    assert rows[0]["known_route_flags"] == ["knowledge_agent_cycle"]
    assert len(rows[0]["command_digest"]) == 16


def test_process_argv_are_never_printed_or_passed_through():
    raw = (
        "python /private/knowledge_agent_cycle --token super-secret\n"
        "python /private/newsletter_process_queue --user private-person\n"
        "python /home/unknown/harmless_agent.py\n"
    )
    result = observer.safe_processes(raw)
    assert result["inspected"] == 3
    assert result["route_match_counts"]["knowledge_agent_cycle"] == 1
    assert result["route_match_counts"]["newsletter_process_queue"] == 1
    assert "super-secret" not in json.dumps(result)
    assert "private-person" not in json.dumps(result)
    assert result["process_identity_proven"] is False


def test_service_names_are_only_reported_as_digests():
    rows = observer.safe_service_units(
        "newsletter_process_queue-private.service loaded active running Private secret\n"
        "other.service loaded active running Unrelated\n"
    )
    assert len(rows) == 1
    assert rows[0]["active"] == "active"
    assert "newsletter_process_queue-private" not in json.dumps(rows)


@pytest.mark.parametrize("role,user", [
    ("vps", "wrong-user"),
    ("cpanel", "githubops"),
])
def test_wrong_user_fails_before_any_host_inventory(tmp_path, role, user):
    with patch.object(observer, "call_readonly", side_effect=AssertionError("host IO")):
        with pytest.raises(PermissionError, match="WRONG_HOST_USER"):
            observer.collect(role, username=user, home=tmp_path)


def test_missing_cron_and_systemd_are_unknown_not_attested_absence(tmp_path):
    with patch.object(observer, "call_readonly", side_effect=[
        ("unavailable_or_empty", ""), ("observed", ""), ("unavailable", ""),
        ("unavailable", ""),
    ]):
        result = observer.collect("vps", username="githubops", home=tmp_path)
    assert result["cron"]["state"] == "unavailable_or_empty"
    assert result["cron"]["enumerated_entries"] is None
    assert result["user_services"]["state"] == "unavailable"
    assert result["attestation"]["external_schedulers_fully_enumerated"] is False
    assert result["attestation"]["automatic_deactivation_authorized"] is False
    assert result["read_only"] and not result["database_queried"]


def test_both_known_roles_are_observed_without_database_or_network(tmp_path):
    with patch.object(observer, "call_readonly", side_effect=[
        ("observed", "0 0 * * * python manage.py knowledge_agent_cycle\n"),
        ("observed", "python manage.py knowledge_agent_cycle\n"),
        ("observed", ""),
        ("observed", "mojtaba-bot-ai.service loaded active running Canonical worker\n"),
    ]):
        out = observer.collect("cpanel", username="zomorod2", home=tmp_path)
    assert out["host_role"] == "cpanel"
    assert out["cron"]["enumerated_entries"] == 1
    assert out["processes"]["route_match_counts"]["knowledge_agent_cycle"] == 1
    assert len(out["system_services"]["candidate_units"]) == 1
    assert out["system_services"]["candidate_units"][0]["active"] == "active"
    assert out["system_services"]["service_name_indicators_only"] is True
    assert out["attestation"]["canonical_worker_executed"] is False
    assert out["attestation"]["handoff_verified"] is False


def test_installed_source_digest_is_full_and_changes_with_source(tmp_path):
    root = tmp_path / "factory-runtime/django-app/core"
    root.mkdir(parents=True)
    file = root / "unified_bot_identity.py"
    file.write_text("BOT_CODE='mojtaba-bot-ai'\n", encoding="utf-8")
    observed = observer.safe_source_digests(tmp_path, "vps")
    digest = observed["unified_bot_identity.py"]["sha256"]
    assert len(digest) == 64
    file.write_text("BOT_CODE='new'\n", encoding="utf-8")
    observed_again = observer.safe_source_digests(tmp_path, "vps")
    assert observed_again["unified_bot_identity.py"]["sha256"] != digest


def test_symlinked_source_not_hashed_as_trusted_installed_code(tmp_path):
    root = tmp_path / "Saeit/core"
    root.mkdir(parents=True)
    secret = tmp_path / "secret-file"
    secret.write_text("sensitive", encoding="utf-8")
    (root / "weather_agent.py").symlink_to(secret)
    result = observer.safe_source_digests(tmp_path, "cpanel")
    assert result["weather_agent.py"] == {"state": "unavailable_or_unsafe"}


def test_host_reads_are_fixed_commands_no_shell_or_remote_execution(tmp_path):
    seen = []
    def fake_call(argv, *, timeout=10):
        seen.append(argv)
        return "observed", ""
    with patch.object(observer, "call_readonly", side_effect=fake_call):
        result = observer.collect("vps", username="githubops", home=tmp_path)
    assert seen == [
        ["crontab", "-l"], ["ps", "-eo", "args="],
        ["systemctl", "--user", "list-units", "--type=service",
         "--all", "--plain", "--no-legend", "--no-pager"],
        ["systemctl", "list-units", "--type=service",
         "--all", "--plain", "--no-legend", "--no-pager"],
    ]
    assert result["external_network_used"] is False


def test_crontab_returncode_one_is_not_mistaken_for_confirmed_empty():
    from subprocess import CompletedProcess
    with patch.object(observer.subprocess, "run", return_value=CompletedProcess(
        args=["crontab", "-l"], returncode=1, stdout="",
        stderr="permission denied or no crontab",
    )):
        status, output = observer.call_readonly(["crontab", "-l"])
    assert status == "unavailable_or_empty" and output == ""


def test_symlinked_intermediate_runtime_folder_not_trusted(tmp_path):
    actual = tmp_path / "hidden-runtime"
    (actual / "django-app/core").mkdir(parents=True)
    (actual / "django-app/core/unified_bot_identity.py").write_text(
        "secret", encoding="utf-8",
    )
    (tmp_path / "factory-runtime").symlink_to(actual, target_is_directory=True)
    result = observer.safe_source_digests(tmp_path, "vps")
    assert result["unified_bot_identity.py"]["state"] == "unavailable_or_unsafe"


def test_manual_live_workflow_never_runs_on_pull_request_or_push():
    workflow = (
        ROOT / ".github/workflows/mojtaba-live-topology-readonly.yml"
    ).read_text(encoding="utf-8")
    event_block = workflow.split("on:", 1)[1].split("permissions:", 1)[0]
    assert "workflow_dispatch:" in event_block
    assert "pull_request:" not in event_block
    assert "push:" not in event_block
    assert "ProxyJump saeit-vps" in workflow
    assert "StrictHostKeyChecking yes" in workflow
    assert "MOJTABA_TWO_HOST_OBSERVATION=" in workflow
    assert "automatic_deactivation_authorized" in workflow
    assert "ssh -F" in workflow
    assert "rm -rf --" in workflow  # Only ephemeral CI-runner SSH key material.


def test_private_php_registry_inventory_is_immutable_and_redacted(tmp_path):
    private = tmp_path / ".private" / "zomorod-business"
    private.mkdir(parents=True)
    db = private / "site_agents.sqlite3"
    with sqlite3.connect(db) as connection:
        connection.execute(
            "CREATE TABLE agents (code TEXT PRIMARY KEY, enabled INTEGER)"
        )
        connection.execute("CREATE TABLE runs (status TEXT, detail TEXT)")
        connection.execute("CREATE TABLE site_work_outputs (status TEXT, title TEXT)")
        connection.executemany("INSERT INTO agents VALUES (?, ?)", [
            ("master", 1), ("weather", 0), ("seo", 1), ("unlisted_private", 1)
        ])
        connection.execute(
            "INSERT INTO runs VALUES (?, ?)", ("ok", "private token=secret_value")
        )
        connection.execute(
            "INSERT INTO site_work_outputs VALUES (?, ?)",
            ("review", "Internal campaign with customer's phone number"),
        )
    before_hash = hashlib.sha256(db.read_bytes()).hexdigest()
    before_files = sorted(path.name for path in private.iterdir())
    report = observer.cpanel_php_registry_snapshot(tmp_path)
    after_files = sorted(path.name for path in private.iterdir())
    assert before_files == after_files
    assert hashlib.sha256(db.read_bytes()).hexdigest() == before_hash
    assert report["state"] == "source_registry_snapshot_only"
    assert report["records"] == 4
    assert report["known_roles_found"] == 3
    assert report["enabled_count"] == 3
    assert report["unknown_code_records"] == 1
    assert report["run_status_counts"] == {"ok": 1}
    assert report["recent_worker_output_status_counts"] == {"review": 1}
    assert "unlisted_private" not in json.dumps(report)
    assert "secret_value" not in json.dumps(report)
    assert "phone number" not in json.dumps(report)
    assert report["database_state_proves_live_workers"] is False
    assert report["live_scheduler_verified"] is False


def test_private_php_registry_wal_refuses_stale_snapshot(tmp_path):
    private = tmp_path / ".private" / "zomorod-business"
    private.mkdir(parents=True)
    db = private / "site_agents.sqlite3"
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE agents(code TEXT, enabled INTEGER)")
    (private / "site_agents.sqlite3-wal").write_bytes(b"simulated wal")
    with patch.object(observer.sqlite3, "connect", side_effect=AssertionError(
        "WAL snapshot must never be opened in immutable mode"
    )):
        report = observer.cpanel_php_registry_snapshot(tmp_path)
    assert report["state"] == "wal_present_snapshot_not_consistent"
    assert report["incomplete_wal_snapshot"] is True
    assert report["records"] is None


def test_private_php_registry_missing_file_is_not_zero_agents(tmp_path):
    report = observer.cpanel_php_registry_snapshot(tmp_path)
    assert report["state"] == "private_database_not_observed"
    assert report["records"] is None
    assert report["enabled_count"] is None
    assert report["agent_roles"] == []


def test_private_php_registry_refuses_private_symlinked_parent(tmp_path):
    actual = tmp_path / "secret-parent"
    actual.mkdir()
    (tmp_path / ".private").symlink_to(actual, target_is_directory=True)
    report = observer.cpanel_php_registry_snapshot(tmp_path)
    assert report["state"] == "unsafe_symlink"
    assert report["records"] is None


def test_cpanel_inventory_reports_php_sqlite_as_separate_unverified_source(tmp_path):
    with patch.object(observer, "call_readonly", return_value=("unavailable", "")):
        result = observer.collect("cpanel", home=tmp_path, username="zomorod2")
    assert result["private_php_site_registry"]["state"] == "private_database_not_observed"
    assert result["private_php_site_registry"]["database_state_proves_live_workers"] is False
    assert result["attestation"]["external_schedulers_fully_enumerated"] is False


def test_system_service_matches_are_not_live_execution_attestation(tmp_path):
    with patch.object(observer, "call_readonly", side_effect=[
        ("unavailable", ""),
        ("observed", ""),
        ("unavailable", ""),
        ("observed", "mojtaba-bot-ai.service loaded active running Single bot\n"),
    ]):
        result = observer.collect("vps", username="githubops", home=tmp_path)
    assert result["system_services"]["state"] == "observed"
    assert len(result["system_services"]["candidate_units"]) == 1
    assert result["attestation"]["canonical_worker_executed"] is False
    assert result["attestation"]["handoff_verified"] is False
    assert result["attestation"]["external_schedulers_fully_enumerated"] is False
