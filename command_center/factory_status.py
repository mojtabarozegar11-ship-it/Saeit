"""Private, fail-closed VPS observation reader for staff dashboard.

Observation comes from a separately authenticated GitHub Actions SSH probe.
This is a sampled report, not a live socket or proof of commercial sales.
"""
from datetime import datetime, timezone
from pathlib import Path
import json
import os
import stat

STATUS_FILE = Path.home() / ".mpw-factory-status" / "status.json"
MAX_AGE_SECONDS = 7200


def read_factory_status(now=None):
    unknown = {"state": "unknown", "reason": "no_fresh_authenticated_vps_observation"}
    try:
        p = STATUS_FILE
        if p.is_symlink() or not p.is_file():
            return unknown
        st = p.stat()
        if not stat.S_ISREG(st.st_mode) or st.st_uid != os.getuid() or st.st_size > 8192:
            return unknown
        if stat.S_IMODE(st.st_mode) & 0o077:
            return unknown
        data = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("schema_version") != 1:
            return unknown
        if data.get("source") != "saeit_verified_ssh_vps_sampler":
            return unknown
        at = datetime.fromisoformat(data["observed_at"].replace("Z", "+00:00"))
        if at.tzinfo is None:
            return unknown
        current = now or datetime.now(timezone.utc)
        age = (current - at).total_seconds()
        if age < -60 or age > MAX_AGE_SECONDS:
            return {"state": "stale", "reason": "vps_sample_expired", "observed_at": at.isoformat()}
        pid = data["loop_pid_verified"]
        log_age = data["activity_log_age_seconds"]
        cycle = data["product_cycle"]
        if type(pid) is not bool or type(log_age) is not int or not 0 <= log_age <= 864000:
            return unknown
        if not isinstance(cycle, dict):
            return unknown
        built = cycle["built_product_count"]
        publishable = cycle["publishable_product_count"]
        qa = cycle["artifact_qa_passed"]
        dist = cycle["store_distribution_state"]
        cycle_age = cycle["age_seconds"]
        if not (type(built) is int and type(publishable) is int and
                0 <= built <= 100000 and 0 <= publishable <= built and
                type(qa) is bool and type(cycle_age) is int and 0 <= cycle_age <= 864000):
            return unknown
        if dist not in {"not_connected", "connected", "unknown"}:
            return unknown
        return {
            "state": "observed_running" if pid and log_age <= 600 else "not_recently_verified_running",
            "source": "verified_ssh_vps_snapshot",
            "observed_at": at.isoformat(),
            "sample_age_seconds": int(age),
            "loop_pid_verified": pid,
            "activity_log_age_seconds_at_sample": log_age,
            "product_cycle": {
                "built_product_count": built,
                "publishable_product_count": publishable,
                "artifact_qa_passed": qa,
                "store_distribution_state": dist,
                "state_age_seconds_at_sample": cycle_age,
            },
            "commercial_revenue_verified": False,
        }
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
        return unknown
