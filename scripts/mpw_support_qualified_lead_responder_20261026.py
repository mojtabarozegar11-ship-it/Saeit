#!/usr/bin/env python3
"""Private, bounded MojPlayWin lead acknowledgments for published service enquiries.

Qualified incoming commercial enquiries only; no unsolicited outreach,
financial obligations, customer orders, or changes to site/payment systems.
No customer email address, subject or body is printed or stored in receipts.
"""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import parseaddr
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

HOME = Path("/home/zomorod2")
MAILDIR = HOME / "mail/mojplaywin.com/support"
PRIVATE = HOME / ".private_mojplaywin_main_agents/support-qualified-leads"
RECEIPTS = PRIVATE / "acknowledgements"
LOCK = PRIVATE / ".process.lock"
FROM = "support@mojplaywin.com"
SENDMAIL = Path("/usr/sbin/sendmail")
SLUGS = frozenset((
    "website-doctor", "landing-page-studio", "ai-automation",
    "business-spreadsheets", "website-templates", "social-media-kits",
    "resume-builder", "logo-studio", "browser-games", "marketing-ai",
    "business-calculators", "website-care",
))
ADDR = re.compile(r"\A[A-Za-z0-9.!#$%&'*+/=?^_{}|~-]+@[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?\.[A-Za-z]{2,40}\Z")
MAX_PER_RUN = 3
MAX_PER_DAY = 8
MAX_MESSAGE = 256000


def safe_dir(path: Path, create=False):
    if path.is_symlink():
        raise RuntimeError("Unsafe symlink in private mail processing path")
    if create:
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(path, 0o700)
    if not path.is_dir() or path.is_symlink():
        raise RuntimeError("Missing or unsafe private directory")


def classified_subject(subject: str):
    value = " ".join(str(subject).split()).casefold()
    if value == "mojplaywin business quote":
        return "business_quote"
    match = re.fullmatch(r"mojplaywin ([a-z0-9-]+) service enquiry", value)
    if match and match.group(1) in SLUGS:
        return match.group(1)
    return None


def is_automated(message):
    auto = str(message.get("Auto-Submitted", "")).strip().casefold()
    precedence = str(message.get("Precedence", "")).strip().casefold()
    return (auto not in ("", "no")
            or precedence in ("bulk", "list", "junk")
            or message.get("List-Id") is not None
            or message.get("X-Auto-Response-Suppress") is not None
            or str(message.get("Return-Path", "")).strip().lower() == "<>")


def recipient(message):
    _, address = parseaddr(str(message.get("From", "")))
    if not address or len(address) > 250 or not ADDR.fullmatch(address):
        return None
    lower = address.lower()
    if lower.endswith("@mojplaywin.com"):
        return None
    if any(k in lower.split("@", 1)[0] for k in
           ("no-reply", "noreply", "mailer-daemon", "postmaster", "bounce")):
        return None
    return lower


def qualify(raw: bytes):
    try:
        message = BytesParser(policy=policy.default).parsebytes(raw, headersonly=True)
    except (ValueError, UnicodeError, TypeError):
        return None
    if is_automated(message):
        return None
    kind = classified_subject(str(message.get("Subject", "")))
    address = recipient(message)
    return (address, kind) if address and kind else None


def candidates():
    safe_dir(MAILDIR)
    now = datetime.now(timezone.utc)
    found = []
    for kind in ("new", "cur"):
        folder = MAILDIR / kind
        if not folder.is_dir() or folder.is_symlink():
            continue
        for path in folder.iterdir():
            if len(found) >= 300:
                break
            if path.is_symlink() or not path.is_file():
                continue
            if kind == "cur" and ":2," in path.name and "S" in path.name.rsplit(":2,", 1)[-1]:
                continue
            stat = path.stat()
            if not 0 < stat.st_size <= MAX_MESSAGE:
                continue
            if datetime.fromtimestamp(stat.st_mtime, timezone.utc) < now - timedelta(days=10):
                continue
            found.append((stat.st_mtime_ns, path))
    return [path for _, path in sorted(found, key=lambda row: row[0])]


def save_receipt(path, value):
    if path.is_symlink() or not RECEIPTS.is_dir():
        raise RuntimeError("Unsafe receipt destination")
    data = (json.dumps(value, sort_keys=True) + "\n").encode("ascii")
    fd, temp = tempfile.mkstemp(prefix=".ack-", dir=str(RECEIPTS))
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def reply(address, kind):
    msg = EmailMessage()
    msg["From"] = FROM
    msg["To"] = address
    msg["Subject"] = "Re: MojPlayWin " + kind.replace("_", " ")
    msg["Auto-Submitted"] = "auto-replied"
    msg["X-Auto-Response-Suppress"] = "All"
    msg.set_content(
        "Hello,\n\n"
        "Thank you for contacting MojPlayWin. We have received your enquiry "
        "about " + kind.replace("-", " ").replace("_", " ") + ".\n\n"
        "To prepare a useful, accurate proposal, please reply with:\n"
        "1. Your project objective and relevant website URL, if any.\n"
        "2. The exact deliverable or problem you want resolved.\n"
        "3. Your preferred completion timeframe and essential constraints.\n\n"
        "Please do not send passwords, wallet recovery phrases, or sensitive "
        "documents by email. This acknowledgment is not a contract, quotation, "
        "payment request, or guarantee of availability. A specific scope and "
        "price will be agreed before commercial work starts.\n\n"
        "MojPlayWin Customer Support\nsupport@mojplaywin.com\n"
    )
    return msg.as_bytes(policy=policy.SMTP)


def run():
    safe_dir(MAILDIR)
    safe_dir(PRIVATE, create=True)
    safe_dir(RECEIPTS, create=True)
    if LOCK.is_symlink():
        raise RuntimeError("Unsafe lock")
    fd = os.open(str(LOCK), os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
    metrics = {"qualified_seen": 0, "queued_to_local_mta": 0,
               "previously_processed": 0, "skipped_unqualified": 0,
               "delivery_not_confirmed": True, "no_customer_information_logged": True}
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        for path in candidates():
            try:
                raw = path.read_bytes()
            except OSError:
                continue
            details = qualify(raw)
            if details is None:
                metrics["skipped_unqualified"] += 1
                continue
            metrics["qualified_seen"] += 1
            address, kind = details
            digest = hashlib.sha256(raw).hexdigest()
            marker = RECEIPTS / (digest + ".json")
            if marker.exists() or marker.is_symlink():
                metrics["previously_processed"] += 1
                continue
            day_start = datetime.now(timezone.utc) - timedelta(hours=24)
            if sum(1 for other in RECEIPTS.iterdir()
                   if other.is_file() and not other.is_symlink()
                   and datetime.fromtimestamp(other.stat().st_mtime, timezone.utc) > day_start) >= MAX_PER_DAY:
                break
            if metrics["queued_to_local_mta"] >= MAX_PER_RUN:
                break
            save_receipt(marker, {"source_sha256": digest, "status": "reserved_before_send",
                                  "kind": kind, "time_utc": datetime.now(timezone.utc).isoformat()})
            try:
                if SENDMAIL.is_symlink() or not SENDMAIL.is_file():
                    raise RuntimeError("MTA_unavailable")
                sent = subprocess.run([str(SENDMAIL), "-oi", "-t"],
                                      input=reply(address, kind), capture_output=True,
                                      timeout=20, check=False)
                status = "accepted_by_local_mta" if sent.returncode == 0 else "mta_refused"
            except (OSError, subprocess.TimeoutExpired, RuntimeError):
                status = "mta_unavailable_or_timeout"
            save_receipt(marker, {"source_sha256": digest, "status": status,
                                  "kind": kind, "time_utc": datetime.now(timezone.utc).isoformat()})
            if status == "accepted_by_local_mta":
                metrics["queued_to_local_mta"] += 1
    finally:
        os.close(fd)
    print("MPW_QUALIFIED_LEAD_ACK=" + json.dumps(metrics, sort_keys=True))
    return metrics


if __name__ == "__main__":
    try:
        run()
    except (RuntimeError, OSError, ValueError, TypeError):
        print("MPW_QUALIFIED_LEAD_ACK_BLOCKED=operational_failure", file=sys.stderr)
        raise SystemExit(2)
