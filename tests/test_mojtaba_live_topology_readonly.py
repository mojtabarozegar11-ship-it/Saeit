"""Offline regressions for the non-mutating two-host canonical topology observer."""
from __future__ import annotations

import importlib.util
import json
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
        ("unavailable_or_empty", ""), ("observed", ""), ("unavailable", "")
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
    ]):
        out = observer.collect("cpanel", username="zomorod2", home=tmp_path)
    assert out["host_role"] == "cpanel"
    assert out["cron"]["enumerated_entries"] == 1
    assert out["processes"]["route_match_counts"]["knowledge_agent_cycle"] == 1
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
