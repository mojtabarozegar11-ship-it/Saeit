"""Canonical bot may replace only the MojPlayWin *history collector*.

Explicitly NOT a migration of private Gen64/Gen65 agents or 77 modules. Refuse
while the old Cron is still installed. Only approved cPanel owner may run;
the central VPS never participates. No free-form command/path arguments.
"""
from __future__ import annotations

import os
from pathlib import Path
import pwd
import subprocess

from .models import Agent, AuditLog
from .mojtaba_site_fleet import CANONICAL_BOT, SiteFleetError

OWNER = "zomorod2"
HOME = Path("/home/zomorod2")
LEGACY_CRON_MARKER = "MPW_MAIN_AGENT_DASHBOARD_COLLECTOR_20261018"


def validate_private_mpw_context(*, username, home, cron_text, private_dir_valid):
    if username != OWNER or Path(home) != HOME:
        raise SiteFleetError("MPW_PRIVATE_COLLECTOR_WRONG_HOST")
    if cron_text is None or not isinstance(cron_text, str):
        raise SiteFleetError("MPW_CRON_INVENTORY_UNAVAILABLE")
    if not private_dir_valid:
        raise SiteFleetError("MPW_PRIVATE_TENANT_DIR_UNSAFE")
    running_lines = [
        line for line in cron_text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    if any(LEGACY_CRON_MARKER in line or "mpw_monitor_collector.py" in line
           for line in running_lines):
        raise SiteFleetError("MPW_LEGACY_COLLECTOR_CRON_STILL_ACTIVE")
    return {"tenant": "mojplaywin", "single_writer_preflight": True,
            "legacy_cron_detected": False}


def collect_private_mpw_as_canonical_bot():
    """The sole explicitly invoked write is the site's existing safe collector.

    Requires a real active canonical bot in the *site* database, exact cPanel
    owner and fixed private directory. This is NEVER invoked by CI/push.
    """
    if os.geteuid() == 0:
        raise SiteFleetError("ROOT_EXECUTION_REFUSED")
    user = pwd.getpwuid(os.geteuid()).pw_name
    from command_center.mpw_private_telemetry import BASE, EVO, HISTORY, collect
    expected = HOME / ".private_mojplaywin_main_agents"
    if BASE != expected or Path.home() != HOME:
        raise SiteFleetError("MPW_SITE_PRIVATE_ROOT_MISMATCH")
    target = BASE / EVO
    try:
        stat_root, stat_evo = BASE.stat(), target.stat()
        valid_dir = (
            BASE.is_dir() and target.is_dir()
            and not BASE.is_symlink() and not target.is_symlink()
            and stat_root.st_uid == os.geteuid()
            and stat_evo.st_uid == os.geteuid()
            and stat_root.st_mode & 0o077 == 0
            and stat_evo.st_mode & 0o077 == 0
        )
    except OSError:
        valid_dir = False
    # A missing crontab is not evidence of zero competing writers.
    try:
        cron = subprocess.run(["crontab", "-l"], capture_output=True,
                              text=True, timeout=8, check=False)
        cron_text = cron.stdout if cron.returncode == 0 else None
    except (subprocess.TimeoutExpired, OSError):
        cron_text = None
    validate_private_mpw_context(
        username=user, home=Path.home(), cron_text=cron_text,
        private_dir_valid=valid_dir,
    )
    if Agent.objects.filter(code="mojtaba-bot-ai", active=True).count() != 1:
        raise SiteFleetError("CANONICAL_SITE_AGENT_NOT_ACTIVE")
    # No user-controlled path, source, tenant, command, or arbitrary delete.
    result = collect()
    if (not isinstance(result, dict)
            or result.get("status") != "private_history_updated"
            or result.get("history") != HISTORY
            or type(result.get("observed")) is not int
            or result["observed"] != 103
            or result.get("public_site_modified") is not False):
        raise SiteFleetError("MPW_PRIVATE_COLLECTOR_RESULT_UNVERIFIED")
    safe = {
        "tenant": "mojplaywin", "canonical_bot": CANONICAL_BOT,
        "collector_action": "private_history_updated",
        "slots_measured": result["observed"],
        "independent_workers_proven": 0,
        "customers_or_orders_modified": False,
        "legacy_files_retired": False,
    }
    AuditLog.objects.create(
        actor_type="system", actor_id="mojtaba-bot-ai",
        action="mojtaba_mpw_site_history_collection",
        target_type="site_private_telemetry", target_id="mojplaywin",
        before_state={}, after_state=safe,
    )
    return safe
