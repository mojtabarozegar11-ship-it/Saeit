"""Offline regressions for the non-mutating two-host canonical topology observer."""
from __future__ import annotations

import importlib.util
import json
import hashlib
import sqlite3
import subprocess
import sys
import textwrap
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


def test_manual_live_workflow_uses_existing_factory_runner_and_unique_push_gate():
    workflow = (
        ROOT / ".github/workflows/mojtaba-live-topology-readonly.yml"
    ).read_text(encoding="utf-8")
    event_block = workflow.split("on:", 1)[1].split("permissions:", 1)[0]
    assert "  workflow_dispatch:" in event_block
    assert "  workflow_call:" in event_block
    assert "  pull_request:" not in event_block
    assert "  schedule:" not in event_block
    # The reviewed one-shot completed. No push-based access to SSH secrets remains.
    assert "  push:" not in event_block
    assert "  pull_request:" not in event_block
    assert "github.repository == 'mojtabarozegar11-ship-it/Saeit'" in workflow
    assert "github.ref == 'refs/heads/main'" in workflow
    assert "audit: run one-time selfhosted read-only cPanel and VPS inventory" not in workflow
    assert "runs-on: [self-hosted, factory-vps]" in workflow
    assert "ProxyJump" not in workflow
    assert "ssh -T -i" in workflow
    assert "-p 1396 zomorod2@178.239.147.125" in workflow
    assert "SHA256:7gQbDdrCVLFQRVdY6DAw8lF70jvlPfbJQslYn787E04" in workflow
    assert "StrictHostKeyChecking=yes" in workflow
    assert "MOJTABA_DISPOSITION_PREVIEW=" in workflow
    assert "automatic_deactivation_authorized" in workflow
    assert "rm -rf --" in workflow  # Ephemeral runner key material only.


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


def test_malformed_php_sqlite_statuses_are_redacted_and_counts_preserved(tmp_path):
    private = tmp_path / ".private" / "zomorod-business"
    private.mkdir(parents=True)
    db = private / "site_agents.sqlite3"
    with sqlite3.connect(db) as connection:
        connection.execute(
            "CREATE TABLE agents (code TEXT PRIMARY KEY, enabled INTEGER)"
        )
        connection.execute("INSERT INTO agents VALUES ('master', 1)")
        connection.execute("CREATE TABLE runs (status TEXT, detail TEXT)")
        connection.execute(
            "CREATE TABLE site_work_outputs (status TEXT, title TEXT)"
        )
        connection.executemany("INSERT INTO runs VALUES (?, '')", [
            ("ok",), ("PRIVATE_KEY_ABC",), ("CLIENT_PHONE_123",),
        ])
        connection.executemany("INSERT INTO site_work_outputs VALUES (?, '')", [
            ("review",), ("SECRET_WALLET_ADDRESS",), ("SECRET_PARTNER",),
        ])
    observed = observer.cpanel_php_registry_snapshot(tmp_path)
    text = json.dumps(observed)
    for secret in (
        "PRIVATE_KEY_ABC", "CLIENT_PHONE_123",
        "SECRET_WALLET_ADDRESS", "SECRET_PARTNER",
    ):
        assert secret not in text
    assert observed["run_status_counts"] == {"ok": 1, "unexpected_status": 2}
    assert observed["recent_worker_output_status_counts"] == {
        "review": 1, "unexpected_status": 2,
    }
    assert observed["records"] == 1


def test_sqlite_status_aggregation_refuses_unapproved_table_names():
    with sqlite3.connect(":memory:") as connection:
        with pytest.raises(ValueError, match="unknown aggregate status table"):
            observer.safe_sqlite_status_counts(connection, "sqlite_master")


def test_selfhost_summary_runs_with_independent_observed_snapshots(tmp_path):
    workflow = (
        ROOT / ".github/workflows/mojtaba-live-topology-readonly.yml"
    ).read_text(encoding="utf-8")
    verifier = workflow.split("<<'SUMMARY'\n", 1)[1].split(
        "\n          SUMMARY", 1
    )[0]
    code = textwrap.dedent(verifier)
    compile(code, "mojtaba_factory_selfhost_summary", "exec")
    with patch.object(observer, "call_readonly", return_value=("unavailable", "")):
        vps = observer.collect("vps", username="githubops", home=tmp_path)
        cpanel = observer.collect("cpanel", username="zomorod2", home=tmp_path)
    for role, record in (("vps", vps), ("cpanel", cpanel)):
        p = tmp_path / (role + ".jsonline")
        p.write_text("MOJTABA_LIVE_TOPOLOGY=" + json.dumps(record) + "\n",
                     encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-", str(tmp_path), "1", "1"], input=code,
        cwd=ROOT, capture_output=True, text=True, check=True, timeout=10,
    )
    records = {}
    for line in result.stdout.splitlines():
        key, payload = line.split("=", 1)
        records[key] = json.loads(payload)
    assert records["MOJTABA_READONLY_VPS"]["agent_live_count"] is None
    assert records["MOJTABA_READONLY_CPANEL"]["agent_live_count"] is None
    assert records["MOJTABA_READONLY_CPANEL"]["retirement_authorized"] is False
    assert records["MOJTABA_READONLY_VPS"]["retirement_authorized"] is False
    assert "vps_key" not in result.stdout

def test_selfhost_summary_keeps_valid_host_when_other_is_unavailable(tmp_path):
    workflow = (
        ROOT / ".github/workflows/mojtaba-live-topology-readonly.yml"
    ).read_text(encoding="utf-8")
    code = textwrap.dedent(workflow.split("<<'SUMMARY'\n", 1)[1].split(
        "\n          SUMMARY", 1
    )[0])
    with patch.object(observer, "call_readonly", return_value=("unavailable", "")):
        cpanel = observer.collect("cpanel", username="zomorod2", home=tmp_path)
    (tmp_path / "cpanel.jsonline").write_text(
        "MOJTABA_LIVE_TOPOLOGY=" + json.dumps(cpanel) + "\n", encoding="utf-8"
    )
    result = subprocess.run(
        [sys.executable, "-", str(tmp_path), "0", "1"], input=code,
        cwd=ROOT, capture_output=True, text=True, check=True, timeout=10,
    )
    assert "MOJTABA_READONLY_VPS=unknown_no_snapshot" in result.stdout
    assert "MOJTABA_READONLY_CPANEL={" in result.stdout
    assert '"retirement_authorized": false' in result.stdout.lower()

def test_factory_readonly_workflow_is_parseable_yaml():
    import shutil
    parser = shutil.which("ruby")
    if parser is None:
        pytest.skip("Ruby not installed")
    path = ROOT / ".github/workflows/mojtaba-live-topology-readonly.yml"
    subprocess.run(
        [parser, "-r", "yaml", "-e", "YAML.load_file(ARGV.fetch(0))", str(path)],
        capture_output=True, check=True, timeout=10, text=True,
    )


def test_factory_runner_credential_use_and_local_vps_probe_remain_nondestructive():
    workflow = (
        ROOT / ".github/workflows/mojtaba-live-topology-readonly.yml"
    ).read_text(encoding="utf-8")
    assert "    if: \"${{" in workflow
    assert "    runs-on: [self-hosted, factory-vps]" in workflow
    assert 'python3 deploy/mojtaba_live_topology_readonly.py --role vps' in workflow
    assert 'secrets.SAEIT_HOST_SSH_PRIVATE_KEY' in workflow
    assert 'secrets.VPS_SSH_PRIVATE_KEY' not in workflow
    assert 'sudo ' not in workflow
    assert 'systemctl restart' not in workflow
    assert 'crontab -e' not in workflow
    assert 'git push' not in workflow
    assert 'MOJTABA_DISPOSITION_PREVIEW=partial_host_observation_not_retirement_proof' in workflow


def test_local_vps_preflight_classifies_runner_user_without_disclosing_identity():
    """Do not silently treat a non-githubops self-hosted runner as the VPS app user."""
    workflow = (
        ROOT / ".github/workflows/mojtaba-live-topology-readonly.yml"
    ).read_text(encoding="utf-8")
    assert 'if [[ "$(id -un)" != "githubops" ]]; then' in workflow
    assert "MOJTABA_VPS_OBSERVATION=wrong_host_user" in workflow
    assert 'grep -Fqx "MOJTABA_TOPOLOGY_PREFLIGHT=wrong_host_user"' in workflow
    assert workflow.index('if [[ "$(id -un)" != "githubops" ]]') < workflow.index(
        'elif python3 deploy/mojtaba_live_topology_readonly.py --role vps'
    )
    assert 'cat "$d/vps.err"' not in workflow
    assert 'echo "$runner_user"' not in workflow
    assert "sudo " not in workflow


def test_incomplete_two_host_inventory_fails_closed_not_green():
    """A green Actions job must not attest a partial cPanel-only observation."""
    workflow = (
        ROOT / ".github/workflows/mojtaba-live-topology-readonly.yml"
    ).read_text(encoding="utf-8")
    assert '"vps": sys.argv[2] == "1", "cpanel": sys.argv[3] == "1"' in workflow
    assert 'print("MOJTABA_READONLY_" + role.upper() + "="' in workflow
    assert "MOJTABA_DUAL_HOST_GATE=PASS_OBSERVATIONS_ONLY" in workflow
    assert (
        'echo "MOJTABA_DISPOSITION_PREVIEW=partial_host_observation_not_retirement_proof"\n'
        '            echo "MOJTABA_DUAL_HOST_GATE=BLOCKED_INCOMPLETE"\n'
        '            exit 1'
    ) in workflow
    assert "github.ref == 'refs/heads/main'" in workflow
    assert "secrets.VPS_SSH_PRIVATE_KEY" not in workflow
    assert "StrictHostKeyChecking=yes" in workflow
