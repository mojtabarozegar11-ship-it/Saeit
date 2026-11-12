#!/usr/bin/env python3
"""Bounded, read-only, secret-minimal cPanel invoice source evidence.

This script must be streamed to "python3 -B -" on the authorized cPanel host.
It never imports project modules, initializes Django, executes SQL, invokes an
invoice, creates a payment or writes to the application. Output is JSON flags,
fixed source-relative names, SHA-256 digests and function names only.
"""
from __future__ import annotations

import ast
import hashlib
import json
import re
import stat
from pathlib import Path

ROOT = Path("/home/zomorod2/Saeit-staging")
SOURCE_PATHS = (
    "services/mpw_trx_commercial_web.py",
    "services/mpw_trx_commercial_context.py",
    "mpw_commerce/buyer_orders.py",
    "services/mpw_trx_guest_commerce.py",
)
TEMPLATE = "mpw_commerce/templates/mpw_commerce/product_checkout.html"
MAX_FILE_BYTES = 400_000
MAX_HELPERS = 64


def source_bytes(root: Path, relative: str) -> bytes:
    if relative not in (*SOURCE_PATHS, TEMPLATE):
        raise ValueError("OUTSIDE_ALLOWLIST")
    if root.is_symlink() or not root.is_dir():
        raise ValueError("UNSAFE_APPLICATION_ROOT")
    path = root / relative
    if any(part.is_symlink() for part in (path, path.parent, path.parent.parent)):
        raise ValueError("SYMLINK_IN_SOURCE")
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= MAX_FILE_BYTES:
        raise ValueError("INVALID_SOURCE_FILE")
    return path.read_bytes()


def folded_literal(node: ast.AST) -> str | None:
    """Fold only short static string expressions; do not evaluate code."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value if len(node.value) <= 256 else None
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left, right = folded_literal(node.left), folded_literal(node.right)
        if left is not None and right is not None and len(left) + len(right) <= 256:
            return left + right
    if isinstance(node, ast.JoinedStr):
        parts = [folded_literal(part) for part in node.values]
        if all(part is not None for part in parts) and sum(map(len, parts)) <= 256:
            return "".join(parts)
    return None


def has_email_reference(node: ast.AST, constants: dict[str, str] | None = None) -> bool:
    aliases = constants or {}
    for part in ast.walk(node):
        if isinstance(part, ast.Name):
            if "email" in part.id.lower() or "email" in aliases.get(part.id, "").lower():
                return True
        if isinstance(part, ast.Attribute) and "email" in part.attr.lower():
            return True
        if isinstance(part, ast.keyword) and part.arg and "email" in part.arg.lower():
            return True
        if isinstance(part, ast.arg) and "email" in part.arg.lower():
            return True
        folded = folded_literal(part)
        if folded is not None and "email" in folded.lower():
            return True
    return False


def template_email_controls(raw: bytes) -> bool:
    """Detect aliases and hidden email inputs, not just name='email'."""
    for tag in re.finditer(rb"<(?:input|textarea|select|button)\b[^>]{0,4096}>", raw, re.I | re.S):
        opening = tag.group(0)
        for name in (b"name", b"id", b"type", b"autocomplete"):
            pattern = (rb"(?<![\w:-])" + name
                       + rb"""\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s/>]+))""")
            for match in re.finditer(pattern, opening, re.I | re.S):
                val = next((v for v in match.groups() if v is not None), b"").lower()
                if (name in (b"name", b"id") and b"email" in val or
                        name in (b"type", b"autocomplete") and val == b"email"):
                    return True
    return False


def module_report(relative: str, raw: bytes) -> dict:
    tree = ast.parse(raw.decode("utf-8"), filename=relative)
    functions = {
        node.name: node for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    aliases = {}
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            for item in node.names:
                aliases[item.asname or item.name] = (node.module or "") + "." + item.name
        elif isinstance(node, ast.Import):
            for item in node.names:
                aliases[item.asname or item.name.split(".")[0]] = item.name
    constants = {}
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            value = folded_literal(node.value) if node.value is not None else None
            targets = node.targets if isinstance(node, ast.Assign) else (node.target,)
            if value is not None:
                for target in targets:
                    if isinstance(target, ast.Name):
                        constants[target.id] = value
    roots = []
    if relative == SOURCE_PATHS[0]:
        roots = ["_start_order"]
    elif relative == SOURCE_PATHS[2]:
        roots = [name for name in functions if name == "record_invoice"]
    elif relative == SOURCE_PATHS[1]:
        roots = [name for name in functions if "invoice" in name.lower()]
    elif relative == SOURCE_PATHS[3]:
        roots = ["_new_user", "_identity", "patch_commercial"]
    explored = set()
    pending = list(roots)
    email_functions = []
    external_calls = []
    dynamic_calls = False
    while pending and len(explored) < MAX_HELPERS:
        name = pending.pop(0)
        if name in explored:
            continue
        explored.add(name)
        fn = functions.get(name)
        if fn is None:
            continue
        if has_email_reference(fn, constants):
            email_functions.append(name)
        for part in ast.walk(fn):
            if not isinstance(part, ast.Call):
                continue
            if isinstance(part.func, ast.Name):
                callee = part.func.id
                if callee in functions and callee not in explored:
                    pending.append(callee)
                if callee in aliases:
                    external_calls.append({"caller": name,
                                           "import": aliases[callee][:130]})
            elif isinstance(part.func, ast.Attribute):
                if part.func.attr == "record_invoice":
                    external_calls.append({"caller": name,
                                           "import": "qualified.record_invoice"})
            else:
                dynamic_calls = True
    return {
        "file": relative,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "root_functions_found": [name for name in roots if name in functions],
        "root_functions_missing": [name for name in roots if name not in functions],
        "analyzed_local_functions": len(explored),
        "email_referencing_functions": sorted(set(email_functions)),
        "record_invoice_present": "record_invoice" in functions,
        "invoice_import_calls": [
            x for x in external_calls if "invoice" in x["import"].lower()
            or "record" in x["import"].lower()
        ][:15],
        "dynamic_call_observed": dynamic_calls,
        "helper_limit_hit": len(explored) >= MAX_HELPERS,
    }


def inspect(root: Path = ROOT) -> dict:
    files = []
    missing = []
    for relative in SOURCE_PATHS:
        try:
            raw = source_bytes(root, relative)
            files.append(module_report(relative, raw))
        except (OSError, UnicodeError, ValueError, SyntaxError) as exc:
            missing.append({"file": relative, "reason": type(exc).__name__})
    template = {}
    try:
        raw = source_bytes(root, TEMPLATE)
        # Display only source indicators, never render text, tokens or buyer data.
        lowered = raw.lower()
        template = {
            "exists": True, "sha256": hashlib.sha256(raw).hexdigest(),
            "legacy_email_input_marker": b"mpw-buy-email" in lowered,
            "email_name_marker": b'name="email"' in lowered
                                  or b"name='email'" in lowered,
            "email_control_marker": template_email_controls(raw),
            "csrf_template_marker": b"csrf_token" in lowered
                                    or b"csrfmiddlewaretoken" in lowered,
        }
    except (OSError, ValueError) as exc:
        template = {"exists": False, "reason": type(exc).__name__}
    start = next((f for f in files if f["file"] == SOURCE_PATHS[0]), None)
    email_hits = [
        {"file": f["file"], "functions": f["email_referencing_functions"]}
        for f in files if f["email_referencing_functions"]
    ]
    missing_start = not start or "_start_order" not in start["root_functions_found"]
    recorder = next((f for f in files if f["file"] == SOURCE_PATHS[2]), None)
    missing_recorder = not recorder or not recorder["record_invoice_present"]
    email_template = bool(
        template.get("legacy_email_input_marker")
        or template.get("email_name_marker")
        or template.get("email_control_marker")
    )
    missing_csrf = not template.get("csrf_template_marker")
    status = ("SOURCE_MISSING_OR_UNREADABLE" if missing or not template.get("exists")
              else "START_HANDLER_NOT_FOUND" if missing_start
              else "INVOICE_RECORDER_NOT_FOUND" if missing_recorder
              else "EMAIL_REFERENCES_PRESENT" if email_hits
              else "LEGACY_EMAIL_CHECKOUT_PRESENT" if email_template
              else "CHECKOUT_CSRF_MARKER_MISSING" if missing_csrf
              else "DIRECT_SOURCE_CLEAN_EXTERNAL_HELPERS_UNVERIFIED")
    return {
        "mode": "readonly_ast_no_import_no_db_no_payment",
        "status": status,
        "safe_to_deploy": False,
        "real_invoice_post_tested": False,
        "paid_receipt_download_tested": False,
        "files": files,
        "source_problems": missing,
        "template": template,
        "checkout_source_requires_email": email_template,
        "invoice_recorder_found": not missing_recorder,
        "csrf_template_marker_found": not missing_csrf,
        "email_hit_functions": email_hits,
        "external_invoice_code_proven_email_free": False,
    }


def main() -> int:
    report = inspect()
    print("MPW_LIVE_INVOICE_SOURCE_AUDIT=" + json.dumps(report, sort_keys=True))
    # Read-only report runs successfully even when release gate is blocked.
    # Callers must inspect status; exit 0 is NOT a production-readiness signal.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
