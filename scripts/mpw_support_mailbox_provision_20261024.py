#!/usr/bin/env python3
"""One-time, idempotent MojPlayWin cPanel support mailbox provisioning.

Runs exclusively in the cPanel account through a host-key-pinned SSH relay.
Never logs passwords, mail, recipients, session tokens, or message metadata.
Does not alter mail routing, existing accounts, DNS, catch-all, or forwarders.
"""
from __future__ import annotations

import json
import secrets
import subprocess
import sys

DOMAIN = "mojplaywin.com"
LOCAL = "support"
ADDRESS = LOCAL + "@" + DOMAIN
QUOTA_MB = 1024


def status(step, value):
    print("MPW_SUPPORT_" + step + "=" + str(value).lower(), flush=True)


def call_uapi(function, fields=None, json_stdin=False, timeout=40):
    cmd = ["uapi", "--output=json"]
    if json_stdin:
        cmd.insert(1, "--input=json")
    cmd.extend(["Email", function])
    if fields and not json_stdin:
        cmd.extend(k + "=" + str(v) for k, v in fields.items())
    payload = json.dumps(fields).encode("utf-8") if json_stdin else None
    try:
        p = subprocess.run(cmd, input=payload, stdout=subprocess.PIPE,
                           stderr=subprocess.DEVNULL, check=False, timeout=timeout)
        if p.returncode != 0 or len(p.stdout) > 2_000_000:
            return False, None
        obj = json.loads(p.stdout.decode("utf-8"))
        result = obj.get("result") or {}
        return result.get("status") in (1, True), result.get("data")
    except (OSError, subprocess.TimeoutExpired, ValueError, UnicodeError, TypeError):
        return False, None


def account_is_present(rows):
    if not isinstance(rows, list):
        raise RuntimeError("account_list_unavailable")
    return any(
        str(row.get("email") or row.get("login") or row.get("user") or "").lower()
        in (LOCAL, ADDRESS)
        for row in rows if isinstance(row, dict)
    )


def main():
    ok, rows = call_uapi("list_pops", {"domain": DOMAIN})
    if not ok:
        status("PRECHECK", "failed")
        return 11
    if account_is_present(rows):
        status("PROVISION", "already_exists_no_change")
        return verify()

    # Fail closed unless credentials can be transmitted via stdin,
    # avoiding cleartext secrets in CLI argument vectors/process listings.
    input_ok, input_rows = call_uapi(
        "list_pops", {"domain": DOMAIN}, json_stdin=True)
    if not input_ok or not isinstance(input_rows, list):
        status("JSON_STDIN", "unsupported_no_change")
        return 12
    if account_is_present(input_rows):
        status("PROVISION", "already_exists_no_change")
        return verify()

    # Fresh high-entropy password is confined to process memory on cPanel.
    # Owner accesses Webmail from cPanel > Email Accounts > Check Email;
    # owner may set a new password in cPanel > Manage for direct login.
    password = secrets.token_urlsafe(48)
    created, _ = call_uapi(
        "add_pop",
        {"email": LOCAL, "domain": DOMAIN, "password": password,
         "quota": QUOTA_MB, "send_welcome_email": 0},
        json_stdin=True, timeout=60,
    )
    password = None  # Do not persist a credential to a repository or logfile.
    if not created:
        status("PROVISION", "failed_check_cpanel_limits")
        return 13
    status("PROVISION", "created")
    return verify()


def verify():
    ok, rows = call_uapi("list_pops", {"domain": DOMAIN})
    good = bool(ok and account_is_present(rows))
    status("ACCOUNT_CONFIRMED", good)
    ok_forwarder, forwarders = call_uapi(
        "list_forwarders", {"domain": DOMAIN})
    if ok_forwarder and isinstance(forwarders, list):
        support_forwarder = any(
            str(row.get("email") or row.get("forward") or
                row.get("from") or row.get("source") or "").lower()
            in (LOCAL, ADDRESS) for row in forwarders if isinstance(row, dict))
        status("EXISTING_FORWARDER", support_forwarder)
    else:
        status("FORWARDER_CHECK", "unavailable")
    # Never display private forwarding destinations or message content.
    status("ACCESS_PATH", "cpanel_email_accounts_check_email")
    status("PASSWORD_EXPOSED", False)
    status("DNS_OR_ROUTING_CHANGED", False)
    return 0 if good else 14


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, RuntimeError, TypeError, ValueError):
        status("PROVISION", "stopped_safely")
        sys.exit(15)
