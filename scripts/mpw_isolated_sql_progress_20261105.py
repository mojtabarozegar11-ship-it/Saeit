#!/usr/bin/env python3
"""Private SQL stdin->stdout relay with bounded, content-free progress.

Run between the pinned VPS decrypt stream and the *isolated* MariaDB client.
Never parse, persist or log SQL, credentials, customer rows, table names or
hashes. stderr contains only fixed text and completed GiB milestones.

The process is diagnostic only. An EOF or byte milestone does not establish
GPG integrity, SQL import success, or a restorable backup. The caller must
require success from the original source, this relay and the SQL consumer.
"""
from __future__ import annotations

import os
import sys


GIB = 1024 ** 3
MAX_BYTES = 48 * GIB
BLOCK = 1024 * 1024


def relay(source, destination, notice, *, milestone=GIB, maximum=MAX_BYTES):
    """Copy every byte, handling short writes and reporting sizes only."""
    if not 0 < milestone <= maximum:
        raise ValueError("invalid progress bounds")
    count = 0
    next_mark = milestone
    while True:
        payload = source.read(BLOCK)
        if not payload:
            break
        count += len(payload)
        if count > maximum:
            notice("MPW_ISOLATED_SQL_RELAY=LIMIT_EXCEEDED")
            raise ValueError("SQL stream exceeds approved upper bound")
        view = memoryview(payload)
        while view:
            written = destination.write(view)
            if not isinstance(written, int) or written <= 0:
                raise OSError("isolated SQL consumer stopped")
            view = view[written:]
        while count >= next_mark:
            # Production always uses 1 GiB; callers may lower the milestone
            # only for synthetic tests without allocating gigabytes.
            notice("MPW_ISOLATED_SQL_RELAY_GIB=" + str(next_mark // milestone))
            next_mark += milestone
    destination.flush()
    notice("MPW_ISOLATED_SQL_RELAY=EOF_STREAMED_NOT_RESTORE_PROOF")
    return count


def main():
    def notice(message):
        print(message, file=sys.stderr, flush=True)

    try:
        relay(sys.stdin.buffer, sys.stdout.buffer, notice)
    except (BrokenPipeError, OSError, ValueError):
        notice("MPW_ISOLATED_SQL_RELAY=FAILED_NO_RESTORE_CLAIM")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
