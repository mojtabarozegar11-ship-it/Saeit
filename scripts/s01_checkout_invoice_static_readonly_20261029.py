#!/usr/bin/env python3
"""S-01: non-mutating checkout/invoice implementation map from pinned cPanel source.

Never imports Django, touches customer data, prints source lines, reads .env,
queries databases, creates orders, or reveals payment addresses/secrets.
A static call-shape signal is NOT evidence of transaction idempotency.
"""
import ast
import argparse
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
    """Open each component beneath the pinned root without following symlinks.

    Descriptor-relative traversal prevents an intermediate directory symlink
    (or a rename race) from redirecting this diagnostic into unrelated files.
    """
    rel = Path(relative)
    if rel.is_absolute() or not rel.parts or any(part in ("..", ".") for part in rel.parts):
        raise RuntimeError("source path must remain beneath application root")
    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    directory_fd = os.open(root, directory_flags)
    try:
        for part in rel.parts[:-1]:
            next_fd = os.open(part, directory_flags, dir_fd=directory_fd)
            os.close(directory_fd)
            directory_fd = next_fd
        try:
            file_fd = os.open(rel.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                              dir_fd=directory_fd)
        except OSError as exc:
            raise RuntimeError("unsafe or unavailable source file") from exc
        try:
            info = os.fstat(file_fd)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > MAX_BYTES:
                raise RuntimeError("nonregular, linked or oversized source")
            with os.fdopen(os.dup(file_fd), "rb") as stream:
                data = stream.read(MAX_BYTES + 1)
            after = os.fstat(file_fd)
            if (len(data) > MAX_BYTES or len(data) != info.st_size or
                    (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns) !=
                    (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)):
                raise RuntimeError("source changed or grew during read")
            return data
        finally:
            os.close(file_fd)
    finally:
        os.close(directory_fd)

def function_signals(node):
    # A parseable, named function is not a working invoice/download handler.
    # Ignore docstrings and reject common placeholder-only implementations.
    body = list(node.body)
    if body and isinstance(body[0], ast.Expr) and isinstance(
        body[0].value, (ast.Constant,)
    ) and isinstance(body[0].value.value, str):
        body = body[1:]
    # A public invoice/entitlement endpoint consisting only of a constant
    # return or unconditional exception cannot establish a working contract.
    # This is a conservative source-only signal, never proof of correctness.
    is_stub = not body
    if len(body) == 1:
        statement = body[0]
        is_stub = (
            isinstance(statement, (ast.Pass, ast.Raise)) or
            (isinstance(statement, ast.Expr) and
             isinstance(statement.value, ast.Constant) and
             statement.value.value is Ellipsis) or
            (isinstance(statement, ast.Return) and (
                statement.value is None or
                isinstance(statement.value, ast.Constant) or
                (isinstance(statement.value, (ast.List, ast.Tuple, ast.Set))
                 and not statement.value.elts) or
                (isinstance(statement.value, ast.Dict)
                 and not statement.value.keys)
            ))
        )
    calls = []
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            fn = child.func
            calls.append(fn.attr if isinstance(fn, ast.Attribute) else fn.id if isinstance(fn, ast.Name) else "")
    names = set(calls)
    return {
        "is_stub": is_stub,
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
        "source_contract_complete": False, "missing_contract_functions": [],
        "stub_contract_functions": [],
        "safe_to_publish": False,
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
    # A parseable file is not enough: all expected entrypoints must exist.
    # Absence is an explicit release blocker, not a silently green source map.
    found = {
        record["module"]: {fn["name"] for fn in record["functions"] if not fn["is_stub"]}
        for record in result["modules"]
    }
    result["missing_contract_functions"] = sorted(
        module + ":" + name
        for module, names in SELECTED.items()
        for name in names - found.get(module, set())
    )
    result["stub_contract_functions"] = sorted(
        record["module"] + ":" + fn["name"]
        for record in result["modules"] for fn in record["functions"]
        if fn["is_stub"]
    )
    result["source_contract_complete"] = not result["missing_contract_functions"]
    # AST structure cannot prove buyer entitlement, idempotency or delivery.
    result["safe_to_publish"] = False
    return result

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline-root", help="authorized local COPY of app source; never cPanel")
    args = parser.parse_args(argv)
    try:
        # Explicit offline mode cannot be mistaken for a live Passenger audit.
        root = Path(args.offline_root) if args.offline_root else APP
        result = inspect_source(root=root, require_wsg=not bool(args.offline_root))
        result["offline_copy_only"] = bool(args.offline_root)
        result["safe_to_publish"] = False
        print("S01_INVOICE_STATIC_MAP=" + json.dumps(result, sort_keys=True))
        return 0 if result["source_contract_complete"] else 2
    except (OSError, RuntimeError, ValueError):
        print("S01_INVOICE_STATIC_MAP=" + json.dumps({
            "scope": "S01_CHECKOUT_INVOICE_STATIC_READONLY",
            "status": "BLOCKED_SOURCE_UNREADABLE",
            "source_contract_complete": False, "safe_to_publish": False,
        }, sort_keys=True))
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
