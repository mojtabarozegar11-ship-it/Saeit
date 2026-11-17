#!/usr/bin/env python3
"""Convert a fixed, read-only cPanel source inventory into safe public booleans.

Never print source SHA, absolute host paths, secrets, file contents, account
information or any unexpected remote JSON value. The source inspector does not
import Django, inspect a DB, write a file, or interact with payment endpoints.
"""
import json
import sys

from scripts.mpw_private_checkout_live_source_inventory_20261116 import (
    EXPECTED, PREFIX,
)

MAX_INPUT_BYTES = 16384
REPORT_MARKER = "MPW_CPANEL_CHECKOUT_SOURCE_READONLY="


def sanitize(raw):
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_INPUT_BYTES:
        raise ValueError("bounded inventory response required")
    source = raw.decode("utf-8").strip()
    if not source.startswith(PREFIX) or "\n" in source:
        raise ValueError("unexpected remote inventory output")
    doc = json.loads(source[len(PREFIX):])
    if type(doc) is not dict or doc.get("schema") != (
            "mpw.cpanel.checkout.module-inventory.readonly.v1"):
        raise ValueError("wrong inspector schema")
    for field, value in (
        ("read_only", True),
        ("customer_data_read", False),
        ("application_modules_imported", False),
        ("payment_or_invoice_created", False),
        ("host_changed", False),
        ("root_valid", True),
    ):
        if doc.get(field) is not value:
            raise ValueError("untrusted or invalid remote inspection envelope")
    modules = doc.get("modules")
    if type(modules) is not dict or set(modules) != set(EXPECTED):
        raise ValueError("unexpected/missing inventory paths")
    safe = {}
    for relative in EXPECTED:
        entry = modules[relative]
        if type(entry) is not dict:
            raise ValueError("invalid module entry")
        for key in ("present", "regular", "parseable", "exports_present"):
            if type(entry.get(key)) is not bool:
                raise ValueError("invalid module state")
        safe[relative] = {
            "present": entry["present"],
            "parseable": entry["parseable"],
            "exports_present": entry["exports_present"],
        }
    customer = tuple(EXPECTED)[:4]
    return {
        "root_valid": True,
        "customer_sources_present": all(safe[p]["present"] for p in customer),
        "customer_exports_present": all(safe[p]["exports_present"] for p in customer),
        "checkout_source_release_ready": False,
        "modules": safe,
        "payment_performed": False,
        "data_modified": False,
    }


def main():
    try:
        result = sanitize(sys.stdin.buffer.read(MAX_INPUT_BYTES + 1))
    except (ValueError, UnicodeError, json.JSONDecodeError):
        print("MPW_CPANEL_CHECKOUT_SOURCE_READONLY=INVALID_OR_INCOMPLETE")
        return 2
    print(REPORT_MARKER + json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
