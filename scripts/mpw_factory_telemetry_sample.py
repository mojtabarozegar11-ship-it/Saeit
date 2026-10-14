#!/usr/bin/env python3
"""Sample only bounded, non-secret runtime facts from the authorized VPS.

Runs via an authenticated, pinned-host-key SSH session. Prints JSON only.
Does not invoke the factory, mutate its database, or disclose private paths.
"""
import datetime
import json
import os
from pathlib import Path
import time


def sample(home=None, now=None):
    home = home or Path.home()
    now = time.time() if now is None else now
    root = home / "factory-runtime"
    loop = root / "operations/vps-only-loop.sh"
    pidfile = root / "operations/vps-only-loop.pid"
    activity = root / "operations/vps-only-factory.log"
    state = root / "private/autonomous-product-cycle/production-state.json"
    for source in (loop, pidfile, activity, state):
        if not source.is_file() or source.is_symlink():
            raise RuntimeError("Required factory evidence unavailable")
    if not (loop.stat().st_uid == os.getuid() and pidfile.stat().st_uid == os.getuid()):
        raise RuntimeError("Factory owner mismatch")
    if state.stat().st_size > 8192 or pidfile.stat().st_size > 24:
        raise RuntimeError("Oversized factory evidence")

    matched = False
    pid = pidfile.read_text().strip()
    if pid.isascii() and pid.isdecimal():
        proc = Path("/proc") / pid
        try:
            cmd = (proc / "cmdline").read_bytes()
            uid = int((proc / "status").read_text().split("Uid:", 1)[1].splitlines()[0].split()[0])
            matched = bool(b"vps-only-loop.sh" in cmd and uid == os.getuid())
        except (OSError, IndexError, ValueError):
            pass

    production = json.loads(state.read_text(encoding="utf-8"))
    if production.get("mode") != "autonomous_supply_led" or production.get("depends_on_orders") is not False:
        raise RuntimeError("Unexpected product cycle type")
    built = production.get("built_product_count")
    publishable = production.get("publishable_product_count")
    qa = production.get("artifact_qa_passed")
    distribution = production.get("store_distribution_state")
    if not (type(built) is int and type(publishable) is int and 0 <= publishable <= built <= 100000):
        raise RuntimeError("Unexpected product counts")
    if type(qa) is not bool or distribution not in ("not_connected", "connected", "unknown"):
        raise RuntimeError("Unexpected product quality or delivery state")
    def age(path):
        return max(0, min(864000, int(now - path.stat().st_mtime)))
    return {
        "schema_version": 1,
        "source": "saeit_verified_ssh_vps_sampler",
        "observed_at": datetime.datetime.fromtimestamp(now, datetime.timezone.utc).isoformat(),
        "loop_pid_verified": matched,
        "activity_log_age_seconds": age(activity),
        "product_cycle": {
            "built_product_count": built,
            "publishable_product_count": publishable,
            "artifact_qa_passed": qa,
            "store_distribution_state": distribution,
            "age_seconds": age(state),
        },
    }


if __name__ == "__main__":
    print(json.dumps(sample(), sort_keys=True, separators=(",", ":")))
