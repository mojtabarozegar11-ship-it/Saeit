"""Read-only proof that a private cPanel cron release advanced after installation.

Executed inside cPanel via the SSH relay. Only an exit code/fixed marker may
reach GitHub; financial data and reports remain private on the source server.
"""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys

BASE = Path("/home/zomorod2/Saeit-staging/releases")
LINE_RE = re.compile(
    r"/home/zomorod2/Saeit-staging/releases/(business-os-[0-9a-f]{12})/"
    r"scripts/business_os_private_cron\.sh --run cpanel(?:\s|$)"
)
MARKER = "# SAEIT_BUSINESS_OS_PRIVATE_V1"
MAX_BYTES = 256_000


def _time(data):
    raw = data.get("generated_at")
    if not isinstance(raw, str):
        raise ValueError("unknown_time")
    stamp = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if stamp.tzinfo is None:
        raise ValueError("unaware_time")
    return stamp.astimezone(timezone.utc)


def _read_secure_json(path):
    if not path.is_file() or path.is_symlink():
        raise ValueError("missing_report")
    info = path.stat()
    if (info.st_uid != os.geteuid()
            or stat.S_IMODE(info.st_mode) != 0o600
            or not (0 < info.st_size <= MAX_BYTES)):
        raise ValueError("insecure_report")
    return json.loads(path.read_text(encoding="utf-8"))


def advanced_after_install(report, installation_time, now):
    """An observed later receipt is not, by itself, proof of cron causation."""
    captured = _time(report)
    return (captured.timestamp() >= installation_time + 30
            and -60 <= (now - captured).total_seconds() <= 1200)


def verify():
    # Read crontab only. Never install, edit, execute a job, or print its text.
    existing = subprocess.run(["crontab", "-l"], capture_output=True, text=True,
                              timeout=10, check=True).stdout
    marked = [line for line in existing.splitlines() if MARKER in line]
    if len(marked) != 1:
        return 71
    match = LINE_RE.search(marked[0])
    if not match:
        return 71
    root = BASE / match.group(1)
    private = root / "private"
    if (root.is_symlink() or private.is_symlink() or not private.is_dir()
            or private.stat().st_uid != os.geteuid()
            or stat.S_IMODE(private.stat().st_mode) != 0o700):
        return 72
    backups = [path for path in private.glob("cron-before-*")
               if path.is_file() and not path.is_symlink()
               and path.stat().st_uid == os.geteuid()
               and stat.S_IMODE(path.stat().st_mode) == 0o600]
    if not backups:
        return 72
    installed_at = max(path.stat().st_mtime for path in backups)
    now = datetime.now(timezone.utc)
    order_report = _read_secure_json(private / "business-review.json")
    decision = _read_secure_json(private / "decision.json")
    if not str(order_report.get("scope", "")).startswith("local_cpanel_django_only"):
        return 75
    if (decision.get("schema") != "saeit.business-os.private-decision.v1"
            or decision.get("delivery_to_orchestrator") != "not_connected"):
        return 75
    if not advanced_after_install(order_report, installed_at, now):
        return 73
    if not advanced_after_install(decision, installed_at, now):
        return 74
    return 0


def main():
    root = Path(__file__).resolve().parent.parent
    if BASE not in root.parents:
        return 72
    try:
        return verify()
    except Exception:
        return 79


if __name__ == "__main__":
    code = main()
    if code == 0:
        print("BUSINESS_OS_CPANEL_POST_INSTALL_CYCLE_OBSERVED")
    raise SystemExit(code)
