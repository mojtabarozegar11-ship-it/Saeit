#!/usr/bin/env python3
"""Verify one private owner-command receipt without changing its database.

Designed for the already authorized cPanel owner account.  The caller must
provide an exact 32-hex command ID from a trusted private ingress receipt.
This is *not* a substitute for binding that ID to the submitted GitHub comment.
No title, task text, key, or database contents are printed.

  python3 -B scripts/zomorod_verify_private_receipt.py \
    --command-id 0123456789abcdef0123456789abcdef
"""

from __future__ import annotations

import argparse
from contextlib import closing
import os
from pathlib import Path
import pwd
import re
import sqlite3
import stat
import sys


PRIVATE = Path("/home/zomorod2/.private/zomorod-business")
DATABASE = PRIVATE / "command-center.sqlite3"
OWNER = "zomorod2"


class VerificationError(RuntimeError):
    """Non-sensitive failure category."""


def _check_private_db(path: Path) -> None:
    if pwd.getpwuid(os.geteuid()).pw_name != OWNER:
        raise VerificationError("OWNER_IDENTITY_INVALID")
    try:
        info = path.lstat()
        parent = path.parent.lstat()
    except OSError as exc:
        raise VerificationError("DATABASE_UNAVAILABLE") from exc
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_uid != os.geteuid()
        or info.st_mode & (stat.S_IRWXG | stat.S_IRWXO)
        or not stat.S_ISDIR(parent.st_mode)
        or parent.st_uid != os.geteuid()
        or parent.st_mode & (stat.S_IWGRP | stat.S_IWOTH)
    ):
        raise VerificationError("PRIVATE_DATABASE_UNSAFE")


def verify_receipt(db_path: Path, command_id: str) -> None:
    if not re.fullmatch(r"[0-9a-f]{32}", command_id):
        raise VerificationError("COMMAND_ID_INVALID")
    _check_private_db(db_path)
    try:
        # SQLite opens an existing file in read-only mode.  The query-only
        # setting prevents SQL writes even if a future query changes.
        uri = db_path.resolve(strict=True).as_uri() + "?mode=ro"
        with closing(sqlite3.connect(uri, uri=True, timeout=5)) as db:
            db.execute("PRAGMA query_only=ON")
            db.execute("PRAGMA busy_timeout=5000")
            rows = db.execute(
                """
                SELECT r.id
                FROM bridge_receipts AS r
                JOIN tasks AS t ON t.id = r.task_id
                JOIN task_quality AS q ON q.task_id = r.task_id
                WHERE r.id = ?
                  AND t.actor_id = 0
                  AND t.request_key = r.id
                  AND EXISTS (
                    SELECT 1 FROM task_events AS e
                    WHERE e.task_id = t.id
                      AND e.actor_id = 0
                      AND e.kind = 'bridge_signed_task'
                  )
                """,
                (command_id,),
            ).fetchmany(2)
    except sqlite3.Error as exc:
        raise VerificationError("PRIVATE_READBACK_UNAVAILABLE") from exc
    if len(rows) != 1 or rows[0][0] != command_id:
        raise VerificationError("RECEIPT_NOT_INDEPENDENTLY_VERIFIED")
    print("PRIVATE_RECEIPT_READBACK=VERIFIED")
    print("SIGNED_TASK_RECORD=VERIFIED")
    print("DATABASE_MUTATION=NONE")
    print("COMMAND_EXECUTION=NOT_CLAIMED")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--command-id", required=True)
    args = parser.parse_args(argv)
    try:
        verify_receipt(DATABASE, args.command_id)
        return 0
    except VerificationError as exc:
        print("RECEIPT_VERIFICATION_BLOCKED=" + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
