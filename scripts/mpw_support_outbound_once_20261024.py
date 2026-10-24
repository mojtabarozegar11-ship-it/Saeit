#!/usr/bin/env python3
"""Send a single owner-addressed outbound delivery check from cPanel.

Requires the MojPlayWin support mailbox. Never publishes bodies, passwords,
mailbox contents, session identifiers, or delivery secrets to GitHub logs.
"""
from __future__ import annotations
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
import json
import os
import shutil
import subprocess
import sys

DOMAIN = "mojplaywin.com"
SENDER = "support@" + DOMAIN
RECIPIENT = "mojtaba.rozegar11@gmail.com"


def check_account():
    p = subprocess.run(
        ["uapi", "--output=json", "Email", "list_pops", "domain=" + DOMAIN],
        capture_output=True, timeout=18, check=False)
    if p.returncode or len(p.stdout) > 2_000_000:
        return False
    obj = json.loads(p.stdout.decode("utf-8"))
    result = obj.get("result") or {}
    rows = result.get("data")
    return result.get("status") in (1, True) and isinstance(rows, list) and any(
        str(x.get("email") or x.get("login") or x.get("user") or "").lower()
        in ("support", SENDER) for x in rows if isinstance(x, dict))


def main():
    try:
        if not check_account():
            print("MPW_SUPPORT_OUTBOUND_ACCOUNT_PRESENT=false")
            return 11
    except (OSError, ValueError, UnicodeError, subprocess.TimeoutExpired):
        print("MPW_SUPPORT_OUTBOUND_ACCOUNT_PRESENT=unknown")
        return 12
    program = shutil.which("sendmail")
    if not program and os.path.exists("/usr/sbin/sendmail"):
        program = "/usr/sbin/sendmail"
    if not program:
        print("MPW_SUPPORT_OUTBOUND_SENDMAIL_AVAILABLE=false")
        return 13
    message = EmailMessage()
    message["From"] = "MojPlayWin Support <" + SENDER + ">"
    message["To"] = RECIPIENT
    message["Subject"] = "MojPlayWin Support outbound delivery verification – 24 Oct 2026"
    message["Date"] = formatdate(localtime=False)
    message["Message-ID"] = make_msgid(domain=DOMAIN)
    message.set_content(
        "Hello Mojtaba,\n\nThis is a legitimate outbound-delivery "
        "verification from the new MojPlayWin Support mailbox. "
        "No action is required.\n\nMojPlayWin Support\n"
    )
    try:
        p = subprocess.run(
            [program, "-t", "-oi", "-f", SENDER],
            input=message.as_bytes(), stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, timeout=30, check=False)
    except (OSError, subprocess.TimeoutExpired):
        print("MPW_SUPPORT_OUTBOUND_SMTP_ACCEPTED=false")
        return 14
    accepted = p.returncode == 0
    print("MPW_SUPPORT_OUTBOUND_SMTP_ACCEPTED=" + str(accepted).lower())
    print("MPW_SUPPORT_OUTBOUND_CONTENT_OR_CREDENTIALS_LOGGED=false")
    return 0 if accepted else 15


if __name__ == "__main__":
    sys.exit(main())
