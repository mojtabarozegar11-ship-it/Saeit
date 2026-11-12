"""Isolated one-shot direct SSH host observation: no relay, no writes."""
from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
ONESHOT = ROOT / ".github/workflows/mojtaba-one-shot-readonly-dispatch.yml"
MANUAL = ROOT / ".github/workflows/mojtaba-live-topology-readonly.yml"
EXPECTED_COMMIT = "audit: inspect cPanel and VPS independently read-only"


def test_one_shot_yaml_is_real_parseable_yaml():
    ruby = shutil.which("ruby")
    if not ruby:
        pytest.skip("Ruby YAML parser not available on this host")
    subprocess.run(
        [ruby, "-r", "yaml", "-e", "YAML.load_file(ARGV.fetch(0))", str(ONESHOT)],
        check=True, capture_output=True, text=True, timeout=10,
    )


def test_manual_evidence_workflow_remains_untriggered_by_push():
    text = MANUAL.read_text(encoding="utf-8")
    events = text.split("on:\n", 1)[1].split("permissions:", 1)[0]
    assert "  workflow_dispatch:" in events
    assert "  push:" not in events
    assert "  pull_request:" not in events
    assert "  schedule:" not in events


def test_one_shot_is_only_a_single_file_push_on_protected_main():
    text = ONESHOT.read_text(encoding="utf-8")
    event = text.split("on:\n", 1)[1].split("permissions:", 1)[0]
    assert "  push:" in event
    assert "    branches: [main]" in event
    assert '      - ".github/workflows/mojtaba-one-shot-readonly-dispatch.yml"' in event
    for trigger in ("workflow_dispatch:", "pull_request:", "workflow_run:",
                    "issue_comment:", "schedule:"):
        assert f"  {trigger}" not in event


def test_both_host_jobs_require_exact_repository_main_and_unique_subject():
    text = ONESHOT.read_text(encoding="utf-8")
    guards = [s.strip() for s in text.splitlines() if s.strip().startswith("if:")]
    assert len(guards) == 2
    for guard in guards:
        assert guard.startswith('if: "${{')
        assert guard.endswith('}}"')
        assert "github.repository == 'mojtabarozegar11-ship-it/Saeit'" in guard
        assert "github.ref == 'refs/heads/main'" in guard
        assert f"startsWith(github.event.head_commit.message, '{EXPECTED_COMMIT}')" in guard
    assert "  cpanel-readonly:" in text
    assert "  vps-readonly:" in text


def test_hosts_have_separate_job_credentials_and_no_proxy():
    text = ONESHOT.read_text(encoding="utf-8")
    assert "    runs-on: ubuntu-22.04" in text
    assert text.count("    runs-on: ubuntu-22.04") == 2
    assert "secrets.SAEIT_HOST_SSH_PRIVATE_KEY" in text
    assert "secrets.VPS_SSH_PRIVATE_KEY" in text
    assert "ProxyJump" not in text
    assert "secrets: inherit" not in text
    assert text.count("ssh -T -i") == 2
    assert " -p 1396 zomorod2@zohal.pws-dns.net " in text
    assert " -p 22 githubops@178.239.147.150 " in text
    assert text.count("StrictHostKeyChecking=yes") == 2


def test_host_keys_must_match_existing_ssh_fingerprints_before_connecting():
    text = ONESHOT.read_text(encoding="utf-8")
    assert "SHA256:7gQbDdrCVLFQRVdY6DAw8lF70jvlPfbJQslYn787E04" in text
    assert "SHA256:AYdzF3K5uSwAXElE1w/dKo04iT2BbMGwHbRA2Cu4rrs" in text
    assert text.count("ssh-keygen -y") == 2
    assert text.count('echo "MOJTABA_') >= 7


def test_remote_ssh_stdin_only_and_runner_temp_cleanup():
    text = ONESHOT.read_text(encoding="utf-8")
    assert text.count("< deploy/mojtaba_live_topology_readonly.py") == 2
    assert text.count('trap \'rm -rf -- "$d"\' EXIT') == 2
    assert text.count("retirement_authorized\": False") == 2
    assert text.count('"live_agent_count_verified": None') == 2
    for prohibited in (
        "sudo ", "systemctl restart", "systemctl stop", "crontab -e",
        "pip install", "apt install", "git push", "deploy.sh",
        "rm -rf /home", "secrets: inherit",
    ):
        assert prohibited not in text


def test_readonly_source_output_is_schema_and_os_user_verified():
    text = ONESHOT.read_text(encoding="utf-8")
    assert text.count('MOJTABA_LIVE_TOPOLOGY=') == 2
    assert text.count("mojtaba.bot.ai.live-topology-observation.v1") == 2
    assert text.count("expected_user_verified") == 2
    assert text.count("automatic_deactivation_authorized") == 2
    assert "php_enabled_records_not_bots" in text
    assert "MOJTABA_CPANEL_READONLY_RESULT=" in text
    assert "MOJTABA_VPS_READONLY_RESULT=" in text
