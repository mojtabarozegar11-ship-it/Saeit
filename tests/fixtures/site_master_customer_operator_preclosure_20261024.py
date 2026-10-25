#!/usr/bin/env python3
"""Owner-only, API-free customer review completion for two independent sites.

No payment/order operations. A response is displayed only after the customer
authenticates with their original high-entropy ticket ID and email. Does not
send email, trigger a refund, approve payment or mutate the merchant ledger.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import pwd
import re
import sqlite3

HOME = Path("/home/zomorod2")
ROOTS = {
    "zomorod": HOME / ".private/zomorod-business",
    "mojplaywin": HOME / ".private_mojplaywin_main_agents",
}
TICKET_RE = re.compile(r"[0-9a-f]{24}\Z")
REVIEWER_RE = re.compile(r"[a-z][a-z0-9_-]{1,39}\Z")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def ensure_table(db: sqlite3.Connection) -> None:
    db.execute(
        "CREATE TABLE IF NOT EXISTS customer_operator_replies("
        "tenant TEXT NOT NULL,ticket_id TEXT NOT NULL,answer TEXT NOT NULL,"
        "reviewer_code TEXT NOT NULL,reviewed_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,"
        "PRIMARY KEY(tenant,ticket_id),"
        "FOREIGN KEY(ticket_id) REFERENCES customer_questions(id))"
    )


def save_reply(db: sqlite3.Connection, tenant: str, ticket: str,
               answer: str, reviewer: str) -> str:
    require(tenant in ROOTS and isinstance(ticket, str) and
            TICKET_RE.fullmatch(ticket) is not None, "INVALID_SITE_OR_TICKET")
    require(isinstance(reviewer, str) and REVIEWER_RE.fullmatch(reviewer) is not None,
            "INVALID_REVIEWER_CODE")
    require(isinstance(answer, str) and 20 <= len(answer) <= 4000 and
            "\x00" not in answer and "\r" not in answer,
            "ANSWER_LENGTH_OR_ENCODING_INVALID")
    row = db.execute(
        "SELECT processing_status FROM customer_questions WHERE tenant=? AND id=?",
        (tenant,ticket),
    ).fetchone()
    require(row is not None and row[0] == "needs_review",
            "REQUEST_NOT_QUEUED_FOR_PERSONAL_REVIEW")
    ensure_table(db)
    old = db.execute(
        "SELECT answer,reviewer_code FROM customer_operator_replies "
        "WHERE tenant=? AND ticket_id=?", (tenant,ticket),
    ).fetchone()
    if old is not None:
        require(old == (answer,reviewer), "REVIEW_ALREADY_RECORDED_NO_OVERWRITE")
        return "already_recorded"
    db.execute(
        "INSERT INTO customer_operator_replies(tenant,ticket_id,answer,reviewer_code) "
        "VALUES(?,?,?,?)", (tenant,ticket,answer,reviewer),
    )
    return "stored"


def main() -> int:
    parser = argparse.ArgumentParser(description="Private staff-reviewed response, never payment authorization")
    parser.add_argument("--site", required=True, choices=sorted(ROOTS))
    parser.add_argument("--ticket", required=True)
    parser.add_argument("--reply-file", required=True)
    parser.add_argument("--reviewer", default="operator")
    args = parser.parse_args()
    require(pwd.getpwuid(os.geteuid()).pw_name == "zomorod2" and Path.home() == HOME,
            "CPANEL_LOCAL_ACCOUNT_REQUIRED")
    root = ROOTS[args.site]
    require(root.is_dir() and not root.is_symlink() and root.stat().st_mode & 0o007 == 0,
            "PRIVATE_SITE_ROOT_INVALID")
    reply_file = Path(args.reply_file)
    require(reply_file.is_file() and not reply_file.is_symlink() and
            reply_file.parent.resolve() == root.resolve() and
            reply_file.stat().st_mode & 0o077 == 0 and
            reply_file.stat().st_size <= 10000,
            "PRIVATE_OPERATOR_RESPONSE_FILE_REQUIRED")
    answer = reply_file.read_text(encoding="utf-8").strip()
    inbox = root / "master_customer_inbox.sqlite3"
    require(inbox.is_file() and not inbox.is_symlink() and inbox.stat().st_mode & 0o077 == 0,
            "PRIVATE_SITE_INBOX_INVALID")
    os.umask(0o077)
    with sqlite3.connect(str(inbox), timeout=10) as db:
        db.execute("PRAGMA foreign_keys=ON")
        result = save_reply(db,args.site,args.ticket,answer,args.reviewer)
        db.commit()
    print("PRIVATE_CUSTOMER_REVIEW="+args.site+":"+result)
    print("NO_PAYMENT_OR_EMAIL_ACTION=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
