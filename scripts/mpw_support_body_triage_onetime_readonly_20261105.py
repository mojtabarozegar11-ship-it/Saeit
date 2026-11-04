#!/usr/bin/env python3
"""One-time, read-only MojPlayWin support triage. No body/PII leaves cPanel.

Only unread, non-automated support messages whose subjects were previously
classified as potential delivery issues or unknown are inspected. No changes.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from email import policy
from email.parser import BytesParser, BytesHeaderParser
from email.utils import parseaddr
from pathlib import Path
import json
import re

MAILDIR = Path("/home/zomorod2/mail/mojplaywin.com/support")
MAX_MESSAGES = 100
MAX_BYTES = 256_000
MAX_TEXT = 7_000


def output(report):
    print("MPW_SUPPORT_CONTENT_TRIAGE_ONETIME=" + json.dumps(
        report, ensure_ascii=False, sort_keys=True))


def subject_group(header):
    subj = " ".join(str(header.get("Subject", "")).casefold().split())
    auto = str(header.get("Auto-Submitted", "")).casefold().strip()
    precedence = str(header.get("Precedence", "")).casefold().strip()
    sender = parseaddr(str(header.get("From", "")))[1].lower()
    if (auto not in ("", "no") or precedence in ("bulk", "list", "junk")
            or header.get("List-Id") is not None
            or header.get("X-Auto-Response-Suppress") is not None
            or str(header.get("Return-Path", "")).strip() == "<>"
            or not sender or sender.endswith("@mojplaywin.com")):
        return "excluded_automated_or_internal"
    if (subj == "mojplaywin business quote"
            or re.fullmatch(r"mojplaywin [a-z0-9-]+ service enquiry", subj)):
        return "excluded_explicit_service_enquiry"
    if any(term in subj for term in ("download", "delivery", "receipt", "recover",
                                     "access file", "فایل", "دانلود", "دریافت")):
        return "possible_delivery_issue"
    if any(term in subj for term in ("payment", "paid", "trx", "wallet", "transaction",
                                     "checkout", "پرداخت", "تراکنش", "کیف پول")):
        return "excluded_payment_subject"
    if any(term in subj for term in ("order", "buy", "purchase", "price", "invoice",
                                     "quote", "book", "خرید", "سفارش", "قیمت", "فاکتور")):
        return "excluded_sales_subject"
    return "other_unclassified"


def body_text(msg):
    chunks = []
    parts = msg.walk() if msg.is_multipart() else [msg]
    for part in parts:
        if part.get_content_disposition() == "attachment":
            continue
        if part.get_content_type() != "text/plain":
            continue
        try:
            data = part.get_content()
        except (ValueError, UnicodeError, LookupError, TypeError, AttributeError):
            continue
        if isinstance(data, str):
            chunks.append(data[:MAX_TEXT])
        if sum(map(len, chunks)) >= MAX_TEXT:
            break
    return " ".join(chunks)[:MAX_TEXT].casefold()


def issue_class(text):
    if not text.strip():
        return "no_plain_text_evidence"
    delivery = ("download", "delivery", "access", "file", "link",
                "دانلود", "دریافت", "لینک", "فایل")
    negative = ("cannot", "can't", "cant", "unable", "failed", "doesn't work",
                "does not work", "not received", "never received", "missing",
                "not working", "error", "broken", "404", "403", "503",
                "نشد", "نمیشه", "نمی‌شود", "کار نمی‌کند", "دریافت نکردم", "خطا")
    payment = ("payment", "paid", "transaction", "trx", "wallet", "invoice",
               "پرداخت", "تراکنش", "فاکتور", "کیف پول")
    refund = ("refund", "money back", "بازگشت وجه", "استرداد وجه")
    buy = ("how to buy", "i want to buy", "can i buy", "purchase", "price",
           "quote", "میخواهم بخرم", "می‌خواهم بخرم", "قیمت", "خرید")
    promotional = ("seo service", "backlink", "guest post", "marketing agency",
                   "sponsored", "buy followers", "rank your website")
    has = lambda words: any(word in text for word in words)
    if has(refund):
        return "refund_request_claim"
    if has(payment) and has(negative):
        return "payment_problem_claim"
    if has(delivery) and has(negative):
        return "delivery_problem_claim"
    if has(buy):
        return "possible_purchase_interest"
    if has(promotional):
        return "likely_marketing_outreach"
    if has(delivery) or has(payment):
        return "delivery_or_payment_topic_unverified"
    return "no_actionable_signal_identified"


def run():
    report = {
        "available": MAILDIR.is_dir() and not MAILDIR.is_symlink(),
        "mailbox": "support", "inspection_scope": "unread_two_header_categories",
        "no_email_body_or_subject_logged": True, "no_sender_logged": True,
        "no_message_identifier_logged": True, "email_writes": 0,
        "email_sends": 0, "email_deletes": 0, "database_writes": 0,
        "body_only_on_cpanel": True, "category_is_heuristic": True,
        "inspected": 0, "skipped": 0, "truncated": False,
        "by_subject_group_and_body_signal": {}, "over_24h": 0,
    }
    if not report["available"]:
        output(report)
        return
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=30)
    categories = Counter()
    considered = 0
    for directory in ("new", "cur"):
        folder = MAILDIR / directory
        if not folder.is_dir() or folder.is_symlink():
            continue
        for path in folder.iterdir():
            considered += 1
            if considered > MAX_MESSAGES:
                report["truncated"] = True
                break
            if path.is_symlink() or not path.is_file():
                report["skipped"] += 1
                continue
            if directory == "cur" and ":2," in path.name and "S" in path.name.rsplit(":2,", 1)[-1]:
                continue
            try:
                stat = path.stat()
                if not (0 < stat.st_size <= MAX_BYTES):
                    report["skipped"] += 1
                    continue
                at = datetime.fromtimestamp(stat.st_mtime, timezone.utc)
                if at < cutoff:
                    continue
                with path.open("rb") as fh:
                    head = fh.read(12_288)
                rawhead = re.split(rb"\r?\n\r?\n", head, maxsplit=1)[0]
                if len(rawhead) >= 12_288:
                    report["skipped"] += 1
                    continue
                parsed_header = BytesHeaderParser(policy=policy.default).parsebytes(rawhead + b"\r\n\r\n")
                kind = subject_group(parsed_header)
                if kind not in ("possible_delivery_issue", "other_unclassified"):
                    continue
                with path.open("rb") as fh:
                    full = fh.read(MAX_BYTES + 1)
                if len(full) > MAX_BYTES:
                    report["skipped"] += 1
                    continue
                message = BytesParser(policy=policy.default).parsebytes(full)
                signal = issue_class(body_text(message))
                categories[kind + ":" + signal] += 1
                report["inspected"] += 1
                report["over_24h"] += int((now - at).total_seconds() > 86400)
            except (OSError, ValueError, TypeError, UnicodeError):
                report["skipped"] += 1
        if report["truncated"]:
            break
    report["by_subject_group_and_body_signal"] = dict(sorted(categories.items()))
    output(report)


if __name__ == "__main__":
    run()
