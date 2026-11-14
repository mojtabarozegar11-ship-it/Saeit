#!/usr/bin/env python3
"""Read-only cPanel UAPI fallback over verified TLS:2083 when SSH is blocked.

Uses an ALREADY-CONFIGURED GitHub Actions secret CPANEL_API_TOKEN, if present.
Never generates a token, never invokes a mutating UAPI method, never exposes
credentials, filenames, addresses, emails or customer payloads in output.

Bounded GET allowlist:
 - PassengerApps/list_applications (aggregate count only)
 - Email/list_pops?domain=mojplaywin.com (support mailbox boolean only)
 - Fileman/list_files?dir=/home/zomorod2/.private_mojplaywin_main_agents/revenue-inquiries&show_hidden=1
   (aggregate encrypted lead/marker counts only, no file contents).

No redirects and no insecure TLS fallback. UAPI token privilege is generally
account-wide: only an existing owner-authorized credential can be supplied.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import ssl
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, build_opener, HTTPSHandler, HTTPRedirectHandler, ProxyHandler

CPANEL_BASE = "https://zohal.pws-dns.net:2083/execute/"
ACCOUNT = "zomorod2"
DOMAIN = "mojplaywin.com"
PRIVATE_DIR = "/home/zomorod2/.private_mojplaywin_main_agents/revenue-inquiries"
MAX_BYTES = 2_000_000
MAX_ROWS = 10_000
ENTRY_RE = re.compile(r"\A[0-9]{8}-[A-F0-9]{18}\.json\Z")
MARKER_RE = re.compile(r"\A\.owner-dispatched-[a-f0-9]{64}\.json\Z")


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _opener():
    return build_opener(ProxyHandler({}), HTTPSHandler(context=ssl.create_default_context()), _NoRedirect())


def _request(module, function, args, token, *, opener=None):
    allowed = {
        ("PassengerApps", "list_applications"): {},
        ("Email", "list_pops"): {"domain": DOMAIN},
        ("Fileman", "list_files"): {"dir": PRIVATE_DIR, "show_hidden": "1"},
    }
    k = (module, function)
    if k not in allowed or args != allowed[k]:
        raise ValueError("UNAPPROVED_UAPI_READ_FUNCTION")
    if (type(token) is not str or not 8 <= len(token) <= 1024
            or any(ch in token for ch in ("\r", "\n", " ", "\t"))):
        raise ValueError("TOKEN_MISSING_OR_INVALID")
    url = CPANEL_BASE + module + "/" + function
    if args:
        url += "?" + urlencode(args)
    headers = {
        "Authorization": "cpanel " + ACCOUNT + ":" + token,
        "Accept": "application/json",
        "User-Agent": "MPW-Pinned-Read-Only-Revenue-Audit/1",
    }
    req = Request(url, headers=headers, method="GET")
    with (opener or _opener()).open(req, timeout=12) as response:
        if response.getcode() != 200:
            raise ValueError("CPANEL_UNEXPECTED_STATUS")
        raw = response.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("UAPI_RESULT_OVER_SIZE_LIMIT")
    obj = json.loads(raw.decode("utf-8"))
    if not isinstance(obj, dict):
        raise ValueError("UAPI_NOT_A_JSON_OBJECT")
    result = obj.get("result")
    if not isinstance(result, dict) or result.get("status") not in (1, True):
        raise ValueError("UAPI_NOT_SUCCESS")
    return result.get("data")


def _list_of_records(data):
    if not isinstance(data, list) or len(data) >= MAX_ROWS:
        raise ValueError("UAPI_MISSING_OR_TRUNCATED_ROWS")
    if any(not isinstance(row, dict) for row in data):
        raise ValueError("UAPI_BAD_ROW")
    return data


def _mail_summary(data):
    rows = _list_of_records(data)
    return {
        "mailbox_api_available": True,
        "support_mailbox_configured": any(
            str(row.get("email") or row.get("login") or "").casefold() in
            ("support@mojplaywin.com", "support")
            for row in rows
        ),
        "mail_accounts_count": len(rows),
        "mail_received_or_forwarded_verified": False,
    }


def _passenger_summary(data):
    rows = _list_of_records(data)
    # Avoid claiming that the site is running or a URL is correctly routed.
    return {"passenger_api_available": True, "application_rows": len(rows),
            "actual_wsgi_sha256_verified": False,
            "passenger_runtime_functioning_verified": False}


def _lead_summary(data):
    rows = _list_of_records(data)
    names = {}
    for row in rows:
        name = row.get("file") or row.get("name")
        kind = row.get("type")
        if not isinstance(name, str) or kind != "file":
            continue
        if ENTRY_RE.fullmatch(name) or MARKER_RE.fullmatch(name):
            if name in names:
                raise ValueError("DUPLICATE_UAPI_LEAD_ENTRY")
            names[name] = True
    encrypted = [name for name in names if ENTRY_RE.fullmatch(name)]
    markers = {name for name in names if MARKER_RE.fullmatch(name)}
    if len(encrypted) >= MAX_ROWS - 1:
        raise ValueError("TOO_MANY_ENCRYPTED_LEADS")
    matched = 0
    for filename in encrypted:
        marker = ".owner-dispatched-" + hashlib.sha256(filename.encode("ascii")).hexdigest() + ".json"
        if marker in markers:
            matched += 1
    return {
        "encrypted_record_filename_candidates": len(encrypted),
        "marker_filenames_matched": matched,
        "candidate_records_without_dispatch_marker": len(encrypted) - matched,
        "read_mail_contents": False,
        "read_customer_payload": False,
        "dispatch_marker_is_proof_of_delivered_email": False,
        "record_decryption_or_validity_verified": False,
        "lead_age_metrics_available_via_ssh_reader_only": False,
    }


def run(token):
    result = {
        "transport": "CPANEL_TLS_2083_READ_ONLY_UAPI",
        "authenticated_as": None,
        "requested_changes": False,
        "messages_sent": False,
        "payment_processed": False,
        "lead_payload_read": False,
        "merchant_balance_verified": False,
        "status": "unknown",
        "checks": {},
    }
    if not token:
        result["status"] = "no_existing_authorized_token"
        return result
    try:
        for name, fn, args, converter in (
            ("passenger", "list_applications", {}, _passenger_summary),
            ("support", "list_pops", {"domain": DOMAIN}, _mail_summary),
            ("inquiries", "list_files", {"dir": PRIVATE_DIR, "show_hidden": "1"}, _lead_summary),
        ):
            module = {"passenger": "PassengerApps", "support": "Email", "inquiries": "Fileman"}[name]
            try:
                data = _request(module, fn, args, token)
                result["checks"][name] = {"status": "ok", **converter(data)}
            except HTTPError as exc:
                result["checks"][name] = {"status": "http_error", "http_status": int(exc.code)}
            except (URLError, OSError, ValueError, TypeError, UnicodeError, json.JSONDecodeError) as exc:
                result["checks"][name] = {"status": "held", "error_class": type(exc).__name__}
        result["authenticated_as"] = ACCOUNT if any(
            item.get("status") == "ok" for item in result["checks"].values()
        ) else None
        result["status"] = "partial_verified_uapi" if result["authenticated_as"] else "no_verified_api_result"
    except Exception:
        result["status"] = "safe_failure"
    return result


if __name__ == "__main__":
    token = os.environ.get("CPANEL_API_TOKEN", "")
    report = run(token)
    print("MPW_CPANEL_UAPI_READONLY=" + json.dumps(report, sort_keys=True))
    sys.exit(0 if report["status"] in ("partial_verified_uapi", "no_existing_authorized_token") else 2)
