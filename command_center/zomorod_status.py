"""Read only private cPanel evidence; never infer server health from an empty log."""
import json
from datetime import datetime, timezone
from pathlib import Path

from django.conf import settings


def read_zomorod_health():
    path = Path(settings.BASE_DIR).resolve().parent / ".zomorod_watch" / "health.json"
    if not path.is_file() or path.is_symlink() or path.stat().st_size > 262144:
        return [], []
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        stamp = datetime.fromisoformat(value["captured_at"])
        age = (datetime.now(timezone.utc) - stamp).total_seconds()
        if stamp.tzinfo is None or age < -60:
            return [], []
        stale = age > 2400
        failed = value.get("confirmed_root_failure") is True
        root_state = "stale" if stale else ("failed" if failed else (
            "degraded" if value.get("status") == "degraded" else "healthy"))
        passenger = value.get("passenger", {})
        mapping = passenger.get("mapping") == "verified"
        processes = passenger.get("processes")
        cpanel_state = "stale" if stale else (
            "healthy" if mapping and isinstance(processes, int) and processes > 0 and not failed
            else "failed" if failed and passenger.get("recovery") == "restart_requested"
            else "unknown")
        source = "pinned-cpanel-relay+public-https"
        when = stamp.isoformat()
        rows = [
            {"component": "iran_site", "state": root_state, "source": source,
             "observed_at": when, "evidence_id": "zomorod-uptime",
             "detail": "Root HTTPS and Django health, with two-pass verification"},
            {"component": "cpanel", "state": cpanel_state, "source": source,
             "observed_at": when, "evidence_id": "zomorod-passenger",
             "detail": "Passenger app mapping and own lswsgi process count"},
        ]
        history = []
        for item in value.get("history", [])[-96:]:
            if isinstance(item, dict) and item.get("status") in ("healthy", "degraded", "failed"):
                history.append({"time": str(item.get("time", ""))[:40],
                                "status": item["status"],
                                "recovery": item.get("recovery") == "restart_requested"})
        return rows, history
    except (OSError, ValueError, TypeError, KeyError, OverflowError):
        return [], []
