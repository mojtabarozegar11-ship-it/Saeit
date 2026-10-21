#!/usr/bin/env python3
"""Read-only first-byte source diagnostic. No source content leaves cPanel.

The subprocess runs the existing backup SOURCE stream locally and is stopped
after the first output byte (or a short bounded timeout). Neither SQL nor
filenames are logged, transmitted, archived or persisted. No production writes.
"""
from __future__ import annotations

import base64
import os
import select
import signal
import subprocess
import sys
import time

BOOTSTRAP = (
    "import base64,sys;code=sys.argv[1];"
    "sys.argv=[sys.argv[0]]+sys.argv[2:];exec(base64.b64decode(code))"
)


def first_byte_result(command: list[str], timeout_seconds: float) -> str:
    process = subprocess.Popen(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        bufsize=0,
    )
    try:
        assert process.stdout is not None
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            remaining = min(1.0, max(0.0, deadline - time.monotonic()))
            readable, _, _ = select.select([process.stdout], [], [], remaining)
            if readable:
                # Byte remains in memory on cPanel and is immediately discarded.
                sample = os.read(process.stdout.fileno(), 1)
                return "PASS" if sample else "EOF_BEFORE_DATA"
        return "TIMEOUT_NO_SOURCE_BYTE"
    finally:
        if process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait(timeout=5)


def main() -> int:
    if len(sys.argv) == 2 and sys.argv[1] == "selftest":
        good = first_byte_result(
            [sys.executable, "-c", 'import os;os.write(1,b"x")'], 3
        ) == "PASS"
        empty = first_byte_result([sys.executable, "-c", "pass"], 3)
        if good and empty == "EOF_BEFORE_DATA":
            print("FIRST_BYTE_PROBE_SELFTEST=PASS")
            return 0
        print("FIRST_BYTE_PROBE_SELFTEST=FAIL")
        return 1

    if len(sys.argv) != 3 or sys.argv[2] not in ("mysql", "files"):
        print("FIRST_BYTE_PROBE_BAD_ARGUMENTS", file=sys.stderr)
        return 2
    source64, kind = sys.argv[1:]
    if len(source64) > 80000:
        print("FIRST_BYTE_PROBE_BAD_SOURCE_SIZE", file=sys.stderr)
        return 2
    try:
        base64.b64decode(source64, validate=True)
    except ValueError:
        print("FIRST_BYTE_PROBE_BAD_SOURCE_ENCODING", file=sys.stderr)
        return 2
    command = [sys.executable, "-c", BOOTSTRAP, source64, kind]
    result = first_byte_result(command, 32)
    print("SOURCE_FIRST_BYTE_" + kind.upper() + "=" + result, flush=True)
    return 0 if result == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
