#!/usr/bin/env python3
"""S-01: non-mutating checkout/invoice implementation map from pinned cPanel source.

Never imports Django, touches customer data, prints source lines, reads .env,
queries databases, creates orders, or reveals payment addresses/secrets.
A static call-shape signal is NOT evidence of transaction idempotency.
"""
import ast
import hashlib
import json
import os
import stat
from pathlib import Path

ROOT = Path("/home/zomorod2")
APP = ROOT / "Saeit-staging"
WSGI = ROOT / "mojplaywin.com/passenger_wsgi.py"
MAX_BYTES = 200000
SELECTED = {
    "mpw_commerce/invoicing.py": {"reserve_order_invoice"},
    "mpw_commerce/checkout_views.py": {"checkout_invoice", "checkout_status"},
    "mpw_commerce/settlement.py": {"settle_order_invoice"},
    "mpw_commerce/downloads.py": {"download_paid_item"},
    "mpw_commerce/entitlements.py": {"can_access_purchased_digital_item"},
}

def read_regular(root, relative):
    path = root / relative
    if not path.is_relative_to(root):
        raise RuntimeError("path escaped application")
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > MAX_BYTES:
        raise RuntimeError("nonregular, linked or oversized source")
    return path.read_bytes()

def function_signals(node):
    calls = []
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            fn = child.func
            calls.append(fn.attr if isinstance(fn, ast.Attribute) else fn.id if isinstance(fn, ast.Name) else "")
    names = set(calls)
    return {
        "has_create_call": "create" in names,
        "has_get_or_create_call": "get_or_create" in names,
        "has_update_or_create_call": "update_or_create" in names,
        "has_select_for_update_call": "select_for_update" in names,
        "has_atomic_call": "atomic" in names,
        "has_verified_receipt_name": any(
            isinstance(x, ast.Name) and x.id == "CommerceReceipt"
            for x in ast.walk(node)
        ),
    }

def inspect_source(root=APP, require_wsg=True):
    if require_wsg:
        if not stat.S_ISDIR(root.lstat().st_mode) or root.is_symlink():
            raise RuntimeError("application root invalid")
        wsgi = read_regular(WSGI.parent, WSGI.name)
        if b"APP='/home/zomorod2/Saeit-staging'" not in wsgi:
            raise RuntimeError("Passenger application root mismatch")
    result = {
        "scope": "S01_CHECKOUT_INVOICE_STATIC_READONLY",
        "source_only": True, "database_identity_verified": False,
        "invoice_idempotency_verified": False, "buyer_delivery_verified": False,
        "customer_data_accessed": False, "orders_created": 0, "payments_created": 0,
        "source_modified": False, "modules": [],
    }
    for rel, names in SELECTED.items():
        record = {"module": rel, "exists": False, "functions": []}
        try:
            data = read_regular(root, rel)
        except (OSError, RuntimeError):
            result["modules"].append(record)
            continue
        record["exists"] = True
        record["sha256"] = hashlib.sha256(data).hexdigest()
        try:
            tree = ast.parse(data.decode("utf-8"), filename="<redacted-app-source>")
        except (UnicodeError, SyntaxError):
            record["parse_ok"] = False
            result["modules"].append(record)
            continue
        record["parse_ok"] = True
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names:
                record["functions"].append({"name": node.name, **function_signals(node)})
        result["modules"].append(record)
    return result

if __name__ == "__main__":
    print("S01_INVOICE_STATIC_MAP=" + json.dumps(inspect_source(), sort_keys=True))
