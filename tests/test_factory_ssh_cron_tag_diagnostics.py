"""Offline regressions for read-only VPS health Cron output classification.

No server, key, network, cron installation, or service access in these tests.
"""
from pathlib import Path
import subprocess

WORKFLOW = (Path(__file__).resolve().parents[1] /
            ".github/workflows/vps-direct-ssh-system-health-readonly-20261031.yml")


def _cron_classification_awk() -> str:
    source = WORKFLOW.read_text(encoding="utf-8")
    marker = """          # Safe numeric-only Cron tag categories (no commands or paths).
          printf '%s\\n' "$cron" | awk '
"""
    assert source.count(marker) == 1
    tail = source.split(marker, 1)[1]
    terminator = "\n          '\n"
    assert terminator in tail
    return tail.split(terminator, 1)[0]


def _run_awk(cron_lines: str) -> str:
    proc = subprocess.run(
        ["awk", _cron_classification_awk()], input=cron_lines,
        capture_output=True, text=True, check=True, timeout=5,
    )
    return proc.stdout.strip()


def test_known_and_unknown_active_tags_are_numeric_only():
    input_rows = """* * * * * /private/master --secret NEVER_PRINT # SAEIT_MASTER_AGENT_V1 SAEIT_FACTORY_EVERY_MINUTE_V1
# * * * * * /private/disabled # SAEIT_FACTORY_LIFECYCLE_12_V1
    # * * * * * /private/disabled-2 # SAEIT_FACTORY_LIFECYCLE_12_V1
0 * * * * /private/warehouse # SAEIT_AUTONOMOUS_PRODUCTS_V2 SAEIT_PRODUCTION_WAREHOUSE_V1
0 3 * * * /private/other # SAEIT_FACTORY_FORTY_FAMILY_MASTER_V1
* * * * * /private/single-product # SAEIT_SINGLE_PRODUCT_FACTORY_V1
"""
    result = _run_awk(input_rows)
    assert result == (
        "HEALTH_FACTORY_TAG_COUNTS=master:1,minute:1,lifecycle:0,"
        "products:1,warehouse:1,other:1"
    )
    assert "/private/" not in result
    assert "NEVER_PRINT" not in result
    assert "SINGLE_PRODUCT_FACTORY" not in result


def test_empty_or_commented_cron_reports_no_active_factory_tags():
    assert _run_awk("") == (
        "HEALTH_FACTORY_TAG_COUNTS=master:0,minute:0,lifecycle:0,"
        "products:0,warehouse:0,other:0"
    )
    assert _run_awk("# SAEIT_MASTER_AGENT_V1\n  # SAEIT_FACTORY_EVERY_MINUTE_V1\n") == (
        "HEALTH_FACTORY_TAG_COUNTS=master:0,minute:0,lifecycle:0,"
        "products:0,warehouse:0,other:0"
    )


def test_existing_fail_closed_policy_and_ssh_identity_unchanged():
    source = WORKFLOW.read_text(encoding="utf-8")
    assert "HEALTH_FACTORY_TAGGED_CRON_ENTRIES=$count" in source
    assert "HEALTH_FACTORY_HOLD_CRON_ENTRIES=$count" in source
    assert "HEALTH_CRITICAL=factory_hold_cron_violation" in source
    assert 'if (( count > 0 )); then echo "HEALTH_CRITICAL=factory_hold_cron_violation"; gate_fail=1; fi' in source
    assert "HEALTH_GATE=FAIL" in source
    assert "HEALTH_GATE=PASS" in source
    assert "github.ref == 'refs/heads/main'" in source
    assert "StrictHostKeyChecking=yes" in source
    assert "githubops@178.239.147.150" in source
    assert "SHA256:AYdzF3K5uSwAXElE1w/dKo04iT2BbMGwHbRA2Cu4rrs" in source
    assert "crontab -e" not in source
    assert "crontab -r" not in source
