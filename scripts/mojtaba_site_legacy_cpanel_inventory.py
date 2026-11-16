#!/usr/bin/env python3
"""cPanel-only inventory of legacy site-agent files and exact Cron markers.

Read-only: never deletes, archives, moves, chmods, rewrites cron, or reads
SQLite/customer files. No VPS assumptions. Candidate paths are pinned to the
two site-specific private subtrees established by earlier release workflows.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import json
import os
import re
import stat
import subprocess

CANONICAL = "mojtaba.bot.ai"
CPANEL_USER_HOME = Path("/home/zomorod2")
FILES = {
    "zomorodmelal": (
        ".private/zomorod-business/site_agents.php",
        ".private/zomorod-business/site_agent_workforce.php",
        ".private/zomorod-business/site_agent_cycle_cli.php",
    ),
    "mojplaywin": (
        ".private_mojplaywin_main_agents/evolution_runtime_20261018/mpw_monitor_collector.py",
    ),
}
CRON_MARKERS = {
    "zomorodmelal": "zm-site-agents-only-v100",
    "mojplaywin": "MPW_MAIN_AGENT_DASHBOARD_COLLECTOR_20261018",
}
MAX_FILE_BYTES = 1_000_000


def classify_file(home: Path, relative: str) -> dict:
    target = home / relative
    current = home
    for part in Path(relative).parts[:-1]:
        current /= part
        if current.is_symlink() or not current.is_dir():
            return {"path_id": relative, "state": "unavailable_or_unsafe_parent",
                    "bytes": None, "sha256": None}
    try:
        mode = os.lstat(target).st_mode
    except FileNotFoundError:
        return {"path_id": relative, "state": "absent_not_proof_of_retirement",
                "bytes": None, "sha256": None}
    except OSError:
        return {"path_id": relative, "state": "unreadable",
                "bytes": None, "sha256": None}
    if not stat.S_ISREG(mode):
        return {"path_id": relative, "state": "symlink_or_not_regular",
                "bytes": None, "sha256": None}
    size = target.stat().st_size
    if not 0 < size <= MAX_FILE_BYTES:
        return {"path_id": relative, "state": "unverified_size",
                "bytes": None, "sha256": None}
    digest = sha256()
    with target.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            digest.update(chunk)
    return {"path_id": relative, "state": "candidate_file_observed_not_redundant",
            "bytes": size, "sha256": digest.hexdigest()}


def scan(home: Path, *, cron_text: str | None) -> dict:
    home = Path(home)
    if home.is_symlink() or not home.is_dir():
        raise ValueError("CPANEL_HOME_INVALID_OR_SYMLINK")
    if cron_text is not None and not isinstance(cron_text, str):
        raise ValueError("CRON_TEXT_INVALID")
    file_results = {
        tenant: [classify_file(home, relative) for relative in relatives]
        for tenant, relatives in FILES.items()
    }
    cron_results = {}
    for tenant, marker in CRON_MARKERS.items():
        if cron_text is None:
            cron_results[tenant] = {"state": "unavailable", "matching_count": None,
                                    "command_digests": []}
            continue
        matches = []
        for line in cron_text.splitlines():
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            if marker in line:
                matches.append(sha256(line.encode("utf-8")).hexdigest())
        cron_results[tenant] = {
            "state": "observed_not_retired",
            "matching_count": len(matches),
            "command_digests": sorted(matches),
            "duplicate_marker": len(matches) > 1,
        }
    return {
        "schema": "mojtaba.bot.ai.cpanel-site-legacy-inventory.v1",
        "canonical_bot": CANONICAL,
        "scope": "cpanel_two_site_agent_subtrees_only",
        "files": file_results,
        "cron": cron_results,
        "candidate_bytes_not_confirmed_reclaimable": sum(
            item["bytes"] for rows in file_results.values() for item in rows
            if item["state"] == "candidate_file_observed_not_redundant"
        ),
        "critical_user_data_read": False,
        "site_files_modified": False,
        "crontab_modified": False,
        "permissions_changed": False,
        "safe_to_delete": False,
    }


def run_on_current_cpanel():
    if Path.home() != CPANEL_USER_HOME or os.geteuid() == 0:
        raise PermissionError("SINGLE_TENANT_NON_ROOT_CPANEL_USER_REQUIRED")
    result = subprocess.run(
        ["crontab", "-l"], capture_output=True, text=True, timeout=10, check=False
    )
    # Nonzero may mean absent cron OR insufficient permissions. No false zero.
    cron = result.stdout if result.returncode == 0 else None
    return scan(CPANEL_USER_HOME, cron_text=cron)


if __name__ == "__main__":
    print(json.dumps(run_on_current_cpanel(), sort_keys=True))
