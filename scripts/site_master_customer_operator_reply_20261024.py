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
    require(row is not None, "REQUEST_NOT_FOUND_IN_THIS_SITE")
    ensure_table(db)
    old = db.execute(
        "SELECT answer,reviewer_code FROM customer_operator_replies "
        "WHERE tenant=? AND ticket_id=?", (tenant,ticket),
    ).fetchone()
    if old is not None:
        require(old == (answer,reviewer), "REVIEW_ALREADY_RECORDED_NO_OVERWRITE")
        return "already_recorded"
    require(row[0] == "needs_review", "REQUEST_NOT_QUEUED_FOR_PERSONAL_REVIEW")
    db.execute("SAVEPOINT operator_close")
    try:
        db.execute(
            "INSERT INTO customer_operator_replies(tenant,ticket_id,answer,reviewer_code) "
            "VALUES(?,?,?,?)", (tenant,ticket,answer,reviewer),
        )
        changed = db.execute(
            "UPDATE customer_questions SET processing_status='handled',"
            "master_processed_utc=CURRENT_TIMESTAMP "
            "WHERE tenant=? AND id=? AND processing_status='needs_review'",
            (tenant,ticket),
        ).rowcount
        require(changed == 1, "CONCURRENT_REVIEW_STATE_CHANGE")
        db.execute("RELEASE operator_close")
    except Exception:
        db.execute("ROLLBACK TO operator_close")
        db.execute("RELEASE operator_close")
        raise
    return "stored"


def list_pending_reviews(db: sqlite3.Connection, tenant: str, limit: int = 50) -> list:
    """Private operator-only queue; no customer data enters CI or public routes."""
    require(tenant in ROOTS and 1 <= limit <= 100, "INVALID_REVIEW_QUEUE_SCOPE")
    ensure_table(db)
    return db.execute(
        "SELECT q.id,q.kind,q.created_utc FROM customer_questions q "
        "LEFT JOIN customer_operator_replies r ON r.tenant=q.tenant AND r.ticket_id=q.id "
        "WHERE q.tenant=? AND q.processing_status='needs_review' AND r.ticket_id IS NULL "
        "ORDER BY q.created_utc,q.id LIMIT ?", (tenant,limit),
    ).fetchall()


def main() -> int:
    parser = argparse.ArgumentParser(description="Private staff-reviewed response, never payment authorization")
    parser.add_argument("--site", required=True, choices=sorted(ROOTS))
    parser.add_argument("--ticket")
    parser.add_argument("--reply-file")
    parser.add_argument("--list-pending", action="store_true")
    parser.add_argument("--reviewer", default="operator")
    args = parser.parse_args()
    require(pwd.getpwuid(os.geteuid()).pw_name == "zomorod2" and Path.home() == HOME,
            "CPANEL_LOCAL_ACCOUNT_REQUIRED")
    root = ROOTS[args.site]
    require(root.is_dir() and not root.is_symlink() and root.stat().st_mode & 0o007 == 0,
            "PRIVATE_SITE_ROOT_INVALID")
    inbox = root / "master_customer_inbox.sqlite3"
    require(inbox.is_file() and not inbox.is_symlink() and inbox.stat().st_mode & 0o077 == 0,
            "PRIVATE_SITE_INBOX_INVALID")
    require(not args.list_pending or (args.ticket is None and args.reply_file is None),
            "INVALID_QUEUE_FLAGS")
    require(args.reply_file is None or args.ticket is not None, "TICKET_REQUIRED_FOR_REPLY")
    require(args.list_pending or args.ticket is not None, "TICKET_OR_QUEUE_ACTION_REQUIRED")
    os.umask(0o077)
    with sqlite3.connect(str(inbox), timeout=10) as db:
        db.execute("PRAGMA foreign_keys=ON")
        if args.list_pending:
            for ticket,kind,created in list_pending_reviews(db,args.site):
                print("PENDING_TICKET="+ticket+" | "+kind+" | "+created)
            print("PRIVATE_REVIEW_QUEUE="+args.site)
            return 0
        require(TICKET_RE.fullmatch(args.ticket) is not None, "INVALID_TICKET")
        if args.reply_file is None:
            row = db.execute(
                "SELECT kind,question,claimed_order_ref,created_utc,processing_status "
                "FROM customer_questions WHERE tenant=? AND id=?",
                (args.site,args.ticket),
            ).fetchone()
            require(row is not None, "PRIVATE_TICKET_NOT_FOUND")
            print("PRIVATE_REVIEW_TICKET="+args.site+":"+args.ticket)
            print("TYPE="+str(row[0]))
            print("QUESTION="+str(row[1]))
            print("CLAIMED_ORDER_REF_UNVERIFIED="+str(row[2]))
            print("CREATED_UTC="+str(row[3]))
            print("STATE="+str(row[4]))
            return 0
        reply_file = Path(args.reply_file)
        require(reply_file.is_file() and not reply_file.is_symlink() and
                reply_file.parent.resolve() == root.resolve() and
                reply_file.stat().st_mode & 0o077 == 0 and
                reply_file.stat().st_size <= 10000,
                "PRIVATE_OPERATOR_RESPONSE_FILE_REQUIRED")
        answer = reply_file.read_text(encoding="utf-8").strip()
        result = save_reply(db,args.site,args.ticket,answer,args.reviewer)
        db.commit()
    print("PRIVATE_CUSTOMER_REVIEW="+args.site+":"+result)
    print("REVIEW_QUEUE_CLOSED_AFTER_VERIFIED_STAFF_RESPONSE=PASS")
    print("NO_PAYMENT_OR_EMAIL_ACTION=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
