#!/usr/bin/env python3
"""Install one strictly validated VPS sample in private cPanel storage.

Read sanitized JSON from stdin; no access to application files or SQL.
The calling workflow establishes both SSH connections with pinned host keys.
"""
import datetime
import json
import os
from pathlib import Path
import stat
import sys
import tempfile


def validate(data):
    if type(data) is not dict or set(data) != {
        "schema_version", "source", "observed_at", "loop_pid_verified",
        "activity_log_age_seconds", "product_cycle"
    }:
        raise ValueError("Telemetry schema mismatch")
    if data["schema_version"] != 1 or data["source"] != "saeit_verified_ssh_vps_sampler":
        raise ValueError("Telemetry provenance mismatch")
    when = datetime.datetime.fromisoformat(data["observed_at"].replace("Z", "+00:00"))
    if when.tzinfo is None:
        raise ValueError("Timestamp missing timezone")
    age = (datetime.datetime.now(datetime.timezone.utc) - when).total_seconds()
    if not -60 <= age <= 300:
        raise ValueError("Telemetry timestamp outside acceptance window")
    if type(data["loop_pid_verified"]) is not bool:
        raise ValueError("PID state invalid")
    if type(data["activity_log_age_seconds"]) is not int or not 0 <= data["activity_log_age_seconds"] <= 864000:
        raise ValueError("Activity age invalid")
    cycle = data["product_cycle"]
    if type(cycle) is not dict or set(cycle) != {
        "built_product_count", "publishable_product_count",
        "artifact_qa_passed", "store_distribution_state", "age_seconds"
    }:
        raise ValueError("Product cycle schema invalid")
    built = cycle["built_product_count"]
    publishable = cycle["publishable_product_count"]
    if type(built) is not int or type(publishable) is not int or not 0 <= publishable <= built <= 100000:
        raise ValueError("Product counts invalid")
    if type(cycle["artifact_qa_passed"]) is not bool:
        raise ValueError("Product QA type invalid")
    if cycle["store_distribution_state"] not in ("not_connected", "connected", "unknown"):
        raise ValueError("Distribution state invalid")
    if type(cycle["age_seconds"]) is not int or not 0 <= cycle["age_seconds"] <= 864000:
        raise ValueError("Product-cycle age invalid")
    return when


def main():
    import pwd
    if pwd.getpwuid(os.getuid()).pw_name != "zomorod2":
        raise RuntimeError("Unauthorized cPanel account")
    body = sys.stdin.buffer.read(4097)
    if len(body) > 4096 or not body.strip():
        raise RuntimeError("Telemetry payload out of bounds")
    parsed = json.loads(body)
    timestamp = validate(parsed)
    directory = Path.home() / ".mpw-factory-status"
    if directory.is_symlink():
        raise RuntimeError("Unsafe status directory")
    directory.mkdir(mode=0o700, exist_ok=True)
    if not directory.is_dir() or directory.stat().st_uid != os.getuid():
        raise RuntimeError("Unsafe status storage")
    directory.chmod(0o700)
    current = directory / "status.json"
    if current.is_symlink() or (current.exists() and not current.is_file()):
        raise RuntimeError("Unsafe existing status file")
    if current.exists() and current.stat().st_uid != os.getuid():
        raise RuntimeError("Existing status ownership mismatch")
    previous = directory / "status.previous.json"
    if previous.is_symlink():
        raise RuntimeError("Unsafe backup file")
    # Keep only the previous private observation for local rollback/audit.
    if current.exists():
        old = current.read_bytes()
        if len(old) <= 8192:
            fd, temp = tempfile.mkstemp(prefix=".previous-", dir=directory)
            with os.fdopen(fd, "wb") as file:
                file.write(old)
            os.chmod(temp, 0o600)
            os.replace(temp, previous)

    normalized = json.dumps(parsed, sort_keys=True, separators=(",", ":")).encode() + b"\n"
    fd, temp = tempfile.mkstemp(prefix=".status-", dir=directory)
    try:
        with os.fdopen(fd, "wb") as file:
            file.write(normalized)
            file.flush()
            os.fsync(file.fileno())
        os.chmod(temp, 0o600)
        os.replace(temp, current)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
    assert stat.S_IMODE(current.stat().st_mode) == 0o600
    assert json.loads(current.read_text()) == parsed
    print("FACTORY_BRIDGE_PRIVATE_STATUS_VERIFIED=True")
    print("FACTORY_BRIDGE_OBSERVATION_TIMESTAMP=" + timestamp.isoformat())
    print("FACTORY_BRIDGE_LOOP_SAMPLE=" + str(parsed["loop_pid_verified"]))
    print("FACTORY_BRIDGE_PRIVATE_PACKAGES=" + str(parsed["product_cycle"]["built_product_count"]))
    print("FACTORY_BRIDGE_PUBLISHABLE_PRODUCTS=" + str(parsed["product_cycle"]["publishable_product_count"]))
    print("FACTORY_BRIDGE_NO_LIVE_DJANGO_FILE_CHANGE=True")


if __name__ == "__main__":
    main()
