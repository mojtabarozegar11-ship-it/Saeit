#!/usr/bin/env python3
"""Bounded, synthetic-only, two-stage SSH pipe diagnostic on a GitHub runner.

No production database query, files, credentials, sites or backups touched.
All SSH stderr is discarded to avoid accidental logging of host details.
Each process has a separate exit code; both must finish inside deadline.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time

SIZE = 16 * 1024 * 1024


def run_once(config: str, encoded_script: str, limit: float = 55.0) -> dict:
    # Scripts transferred as argv are dedicated, reviewed *synthetic-only* code.
    entry = "import base64,sys; code=sys.argv.pop(1); exec(base64.b64decode(code))"
    source_command = ["ssh", "-T", "-F", config, "saeit-cpanel",
                      f"python3 -c '{entry}' '{encoded_script}' produce"]
    dest_command = ["ssh", "-T", "-F", config, "saeit-vps",
                    f"python3 -c '{entry}' '{encoded_script}' consume"]
    started = time.monotonic()
    source = destination = None
    payload = b""
    try:
        source = subprocess.Popen(source_command, stdout=subprocess.PIPE,
                                  stderr=subprocess.DEVNULL)
        destination = subprocess.Popen(dest_command, stdin=source.stdout,
                                       stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        source.stdout.close()  # Destination owns the reader, so SIGPIPE works.
        payload, _ = destination.communicate(timeout=limit)
        remaining = max(0.1, limit - (time.monotonic() - started))
        source.wait(timeout=remaining)
    except (OSError, subprocess.TimeoutExpired):
        for proc in (source, destination):
            if proc is not None and proc.poll() is None:
                proc.kill()
        for proc in (source, destination):
            if proc is not None:
                proc.wait()
        return {"status": "failed_or_timed_out",
                "source_exit": source.returncode if source else None,
                "receiver_exit": destination.returncode if destination else None,
                "elapsed_seconds": round(time.monotonic() - started, 2),
                "checksum_matches": False}
    try:
        result = json.loads(payload)
        okay = (
            source.returncode == 0 and destination.returncode == 0
            and result.get("checksum_matches") is True
            and result.get("bytes_read") == SIZE
        )
    except (ValueError, UnicodeError):
        okay = False
    return {"status": "pass" if okay else "failed_or_timed_out",
            "source_exit": source.returncode, "receiver_exit": destination.returncode,
            "elapsed_seconds": round(time.monotonic() - started, 2),
            "checksum_matches": okay}


def main(args):
    if len(args) != 2:
        raise SystemExit(2)
    config, script = args
    results = [run_once(config, script) for _ in range(2)]
    successful = sum(x["status"] == "pass" for x in results)
    print(json.dumps({
        "classification": "MOJPLAYWIN_SYNTHETIC_TRANSPORT_RELIABILITY",
        "attempts": results, "successful": successful, "attempted": len(results),
        "all_attempts_pass": successful == len(results),
        "production_files_read": False, "db_queries_made": False,
        "backup_written": False, "release_permitted": False,
    }, sort_keys=True))
    return 0 if successful == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
