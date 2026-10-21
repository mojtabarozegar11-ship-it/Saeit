#!/usr/bin/env python3
"""Exercise the actual GPG streaming encryptor with synthetic bytes only.

Runs entirely in a disposable VPS temporary directory; no production file or
database access, and no writes to the existing private backup directory.
"""
from __future__ import annotations

import base64
import os
import sys
import tempfile
from pathlib import Path

SYNTHETIC_SIZE = 8 * 1024 * 1024


def main() -> int:
    if len(sys.argv) != 2 or len(sys.argv[1]) > 120000:
        print("GPG_STREAM_PROBE_BAD_ARGUMENTS", file=sys.stderr)
        return 2
    scope = {"__name__": "mojplaywin_gpg_synthetic_probe_import"}
    try:
        code = base64.b64decode(sys.argv[1], validate=True)
        exec(compile(code, "<gpg-encryptor>", "exec"), scope)
        with tempfile.TemporaryDirectory(prefix="mjwp-synthetic-gpg-probe-") as temp:
            folder = Path(temp)
            home = folder / "gnupg"
            target = folder / "random-fixture.gpg"
            scope["make_private"](home)
            key = os.urandom(32)
            count, digest = scope["encrypt_stream_to_file"](
                sys.stdin.buffer, target, home, key
            )
            verified_count, verified_digest = scope["verify_stream"](
                target, home, key
            )
            expected = SYNTHETIC_SIZE + len(scope["MARKER"])
            if not (
                count == verified_count == expected
                and digest == verified_digest
                and target.stat().st_size > 0
            ):
                print("GPG_STREAM_SYNTHETIC=FAILED", file=sys.stderr)
                return 1
        print("GPG_STREAM_SYNTHETIC=PASS")
        print("GPG_STREAM_INPUT_BYTES_VERIFIED=" + str(expected))
        print("GPG_TEST_DIRECTORY_REMOVED=TRUE")
        return 0
    except Exception:
        # Do not log paths, key contents, source details or recovery material.
        print("GPG_STREAM_SYNTHETIC=FAILED", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
