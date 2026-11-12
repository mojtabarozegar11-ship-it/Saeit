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
import sys
from pathlib import Path
from html.parser import HTMLParser

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
# The independently reviewed guest identity adapter used by the release guard.
APPROVED_GUEST_SHA256 = "11b0aa037c31fbcd1198331444d88426d9b4722d13606a7fda846c8f7601d949"


def source_bytes(root: Path, relative: str) -> bytes:
    if relative not in (*SOURCE_PATHS, TEMPLATE):
        raise ValueError("OUTSIDE_ALLOWLIST")
    if root.is_symlink() or not root.is_dir():
        raise ValueError("UNSAFE_APPLICATION_ROOT")
    # Reject symlink traversal at every level, including nested template roots.
    # Checking only the final parent can miss an ancestor such as
    # /home/zomorod2/Saeit-staging/mpw_commerce -> an outside directory.
    parts = Path(relative).parts
    path = root
    for component in parts:
        path = path / component
        if path.is_symlink():
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


class EmailControlParser(HTMLParser):
    """Handle quoted '>' and arbitrary attribute order safely and read-only."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.found = False

    def handle_starttag(self, tag, attrs):
        if tag not in ("input", "textarea", "select", "button"):
            return
        for name, value in attrs:
            name = name.lower()
            value = (value or "").strip().lower()
            if ((name in ("name", "id") and "email" in value)
                    or (name in ("type", "autocomplete") and value == "email")):
                self.found = True


def template_email_controls(raw: bytes) -> bool:
    parser = EmailControlParser()
    parser.feed(raw.decode("utf-8"))
    parser.close()
    return parser.found


def module_report(relative: str, raw: bytes) -> dict:
    tree = ast.parse(raw.decode("utf-8"), filename=relative)
    definitions = [
        node for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    functions = {node.name: node for node in definitions}
    names = [node.name for node in definitions]
    duplicate_functions = sorted(name for name in set(names) if names.count(name) > 1)
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
    elif relative == SOURCE_PATHS[1]:
        roots = [name for name in functions if "invoice" in name.lower()]
    elif relative == SOURCE_PATHS[3]:
        roots = ["_new_user", "_identity", "patch_commercial"]
    # Invoice recorders may reside in any of the three audited commerce modules.
    if relative in SOURCE_PATHS[:3] and "record_invoice" in functions:
        roots.append("record_invoice")
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
        "invoice_recorder_definition_count": names.count("record_invoice"),
        "start_handler_definition_count": names.count("_start_order"),
        "duplicate_functions": duplicate_functions,
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
        for f in files if f["file"] in SOURCE_PATHS[:3]
        and f["email_referencing_functions"]
    ]
    guest = next((f for f in files if f["file"] == SOURCE_PATHS[3]), None)
    guest_email_indicators = (
        guest["email_referencing_functions"] if guest is not None else []
    )
    # Only the exact reviewed synthetic-email auth adapter may have internal
    # email schema identifiers without being called buyer-email collection.
    reviewed_guest_source = bool(
        guest is not None and guest["sha256"] == APPROVED_GUEST_SHA256
    )
    missing_start = not start or start["start_handler_definition_count"] != 1
    recorder_count = sum(f["invoice_recorder_definition_count"] for f in files
                         if f["file"] in SOURCE_PATHS[:3])
    missing_recorder = recorder_count == 0
    duplicate_recorder = recorder_count > 1
    duplicate_functions = any(f["duplicate_functions"] for f in files)
    truncated_graph = any(f["helper_limit_hit"] for f in files[:3])
    email_template = bool(
        template.get("legacy_email_input_marker")
        or template.get("email_name_marker")
        or template.get("email_control_marker")
    )
    missing_csrf = not template.get("csrf_template_marker")
    status = ("SOURCE_MISSING_OR_UNREADABLE" if missing or not template.get("exists")
              else "DUPLICATE_SOURCE_FUNCTIONS" if duplicate_functions
              else "START_HANDLER_NOT_FOUND" if missing_start
              else "INVOICE_RECORDER_NOT_FOUND" if missing_recorder
              else "INVOICE_RECORDER_DUPLICATED" if duplicate_recorder
              else "EMAIL_REFERENCES_PRESENT" if email_hits
              else "LEGACY_EMAIL_CHECKOUT_PRESENT" if email_template
              else "CHECKOUT_CSRF_MARKER_MISSING" if missing_csrf
              else "UNREVIEWED_GUEST_SOURCE" if not reviewed_guest_source
              else "SOURCE_HELPER_GRAPH_TRUNCATED" if truncated_graph
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
        "invoice_recorder_found": recorder_count == 1,
        "invoice_recorder_definition_count": recorder_count,
        "csrf_template_marker_found": not missing_csrf,
        "email_hit_functions": email_hits,
        "guest_source_matches_reviewed_digest": reviewed_guest_source,
        "guest_internal_email_indicators_review_required": guest_email_indicators,
        "external_invoice_code_proven_email_free": False,
    }


REPORT_PREFIX = "MPW_LIVE_INVOICE_SOURCE_AUDIT="


def validate_remote_report(output: str) -> int:
    """Fail closed on a cPanel diagnostic: source-only evidence cannot clear sales."""
    matches = [
        line[len(REPORT_PREFIX):] for line in output.splitlines()
        if line.startswith(REPORT_PREFIX)
    ]
    if len(matches) != 1 or len(matches[0]) > 160_000:
        print("MPW_SOURCE_GATE=BLOCKED_MISSING_OR_DUPLICATE_REPORT")
        return 20
    try:
        report = json.loads(matches[0])
    except (ValueError, TypeError):
        print("MPW_SOURCE_GATE=BLOCKED_INVALID_JSON")
        return 20
    if not isinstance(report, dict) or report.get("mode") != "readonly_ast_no_import_no_db_no_payment":
        print("MPW_SOURCE_GATE=BLOCKED_UNTRUSTED_REPORT_MODE")
        return 20
    status = report.get("status")
    if not isinstance(status, str) or re.fullmatch(r"[A-Z_]{3,80}", status) is None:
        print("MPW_SOURCE_GATE=BLOCKED_INVALID_SOURCE_STATUS")
        return 20
    if status != "DIRECT_SOURCE_CLEAN_EXTERNAL_HELPERS_UNVERIFIED":
        print("MPW_SOURCE_GATE=BLOCKED_" + status)
        return 21
    # This diagnostic never authenticates a buyer or verifies settlement:
    # a clean static snapshot is not a commercial release decision.
    print("MPW_SOURCE_GATE=UNVERIFIED_EXTERNAL_HELPERS_AND_PAID_RECEIPT")
    return 22


def main() -> int:
    if sys.argv[1:] == ["--validate-report"]:
        return validate_remote_report(sys.stdin.read())
    if sys.argv[1:] and sys.argv[1:] != ["-"]:
        print("MPW_SOURCE_GATE=BLOCKED_INVALID_INVOCATION")
        return 20
    report = inspect()
    print(REPORT_PREFIX + json.dumps(report, sort_keys=True))
    # Remote source inspection is not a sale test. The *local* validator
    # must consume this report and fail until external obligations are proven.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
