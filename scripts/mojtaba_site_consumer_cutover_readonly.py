"""Inventory SITE-specific source consumers that prevent deleting legacy agents.

No network, subprocess, shell, secrets, database, host or VPS access.
This deliberately names a short allowlist of verified independent consumers.
Missing/unreadable source is UNKNOWN, never proof of safe retirement.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import stat

# tuple of exact match strings; their presence is sufficient to BLOCK a cutover.
CONSUMERS = {
    "zomorodmelal": {
        "management_php_console": (
            "content/zomorod-business/app.php",
            ("site_agents.php", "zmAgentRender("),
        ),
        "reinstall_workflow": (
            ".github/workflows/zomorod-site-agent-100-stage-release.yml",
            ("site_agent_cycle_cli.php", "crontab"),
        ),
    },
    "mojplaywin": {
        "staff_dashboard": (
            "command_center/mpw_monitor_views.py",
            ("mpw_private_telemetry import snapshot", "snapshot()"),
        ),
        "private_history_adapter": (
            "command_center/mpw_private_telemetry.py",
            ("agent_dashboard_telemetry.json", "snapshot("),
        ),
        "reinstall_workflow": (
            ".github/workflows/mpw-agent-dashboard-private-collector.yml",
            ("Install and prove isolated", "mpw_private_telemetry.py"),
        ),
    },
}


def read_scoped_source(root: Path, name: str):
    root = Path(root)
    if not root.is_dir() or root.is_symlink():
        return None, "unsafe_repository_root"
    target = root
    for part in Path(name).parts:
        target = target / part
        if target.is_symlink():
            return None, "symlink_refused"
    try:
        st = os.lstat(target)
        if not stat.S_ISREG(st.st_mode) or not 0 < st.st_size < 150_000:
            return None, "unavailable_or_unsafe_file"
        # No symlink swap after the stat.
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(target, flags)
        with os.fdopen(fd, "rb") as stream:
            opened = os.fstat(stream.fileno())
            if (opened.st_dev, opened.st_ino) != (st.st_dev, st.st_ino):
                return None, "changed_during_scan"
            raw = stream.read(150_001)
        if len(raw) != st.st_size or len(raw) > 150_000:
            return None, "changed_during_scan"
        return raw.decode("utf-8", "strict"), "source_read"
    except (OSError, UnicodeError):
        return None, "unavailable_or_unreadable"


def inspect(root: Path):
    sites = {}
    for tenant, consumer_list in CONSUMERS.items():
        entries = {}
        for name, (path, markers) in consumer_list.items():
            source, state = read_scoped_source(root, path)
            if source is None:
                entries[name] = {
                    "state": state, "source_path": path,
                    "source_sha256": None, "dependency_active": None,
                }
            else:
                # Evidence of source dependency is not proof of live execution.
                present = tuple(marker in source for marker in markers)
                entries[name] = {
                    "state": "source_dependency_present" if any(present)
                             else "no_known_marker_in_this_source",
                    "source_path": path,
                    "source_sha256": sha256(source.encode("utf-8")).hexdigest(),
                    "dependency_active": any(present),
                    "matching_known_markers": sum(present),
                }
        unresolved = [
            name for name, info in entries.items()
            if info["dependency_active"] is not False
        ]
        sites[tenant] = {
            "consumers": entries,
            "unresolved_consumer_ids": unresolved,
            "all_declared_consumers_reviewed": not unresolved,
            "host_retirement_authorized": False,
        }
    return {
        "schema": "mojtaba.bot.ai.site-native-source-consumer-audit.v1",
        "scope": "repository_source_only_no_host_scan",
        "sites": sites,
        "source_only_retirement_ready": all(
            x["all_declared_consumers_reviewed"] for x in sites.values()
        ),
        "files_removed": 0, "crons_removed": 0,
        "production_release_approved": False,
        "live_host_cleanup_authorized": False,
    }


def main():
    parser = argparse.ArgumentParser(description="Read-only site agent dependency audit")
    parser.add_argument("--repo-root", default=".")
    args = parser.parse_args()
    print(json.dumps(inspect(Path(args.repo_root)), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
