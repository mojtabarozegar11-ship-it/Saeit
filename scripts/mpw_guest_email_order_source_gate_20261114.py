#!/usr/bin/env python3
"""Read-only guest checkout email-ownership dependency gate.

This scans reviewed source files only. It does not import Django, access a
database, disclose customer details, send email, issue invoices or contact RPC.
Even a complete source contract never certifies a deployed checkout.
"""
from __future__ import annotations

import ast
import json
import stat
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELATIVE = {
    "guest": "services/mpw_trx_guest_commerce.py",
    "recovery": "services/mpw_trx_email_recovery.py",
    "models": "core/guest_recovery_models.py",
    "migration": "core/migrations/0049_mpw_guest_email_recovery.py",
    "registration": "core/models.py",
}
LIMIT = 240_000


def _parse(root: Path, relative: str):
    """Read a bounded regular source file, rejecting symlinks in all parents."""
    if root.is_symlink() or not root.is_dir():
        return None
    current = root
    parts = Path(relative).parts
    if not parts or any(part in ("", ".", "..") for part in parts):
        return None
    for part in parts:
        current = current / part
        if current.is_symlink():
            return None
    try:
        info = current.stat()
        if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= LIMIT:
            return None
        raw = current.read_bytes()
        if len(raw) != info.st_size:
            return None
        return ast.parse(raw.decode("utf-8"))
    except (OSError, UnicodeError, SyntaxError, ValueError):
        return None


def _function(tree, name):
    if tree is None:
        return None
    found = [node for node in tree.body
             if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
             and node.name == name]
    return found[0] if len(found) == 1 else None


def _guarded_dispatch(tree):
    fn = _function(tree, "_dispatch")
    if fn is None or not fn.body:
        return False
    branch = fn.body[0]
    if not (isinstance(branch, ast.If) and isinstance(branch.test, ast.Name)
            and branch.test.id == "create"):
        return False
    bound_import = any(
        isinstance(node, ast.ImportFrom)
        and node.module == "services.mpw_trx_email_recovery"
        and any(alias.name == "bound_checkout" for alias in node.names)
        for node in ast.walk(branch)
    )
    return_bound = any(
        isinstance(node, ast.Return)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id == "bound_checkout"
        for node in ast.walk(branch)
    )
    return bound_import and return_bound


def _guest_email_write(tree):
    fn = _function(tree, "_new_user")
    if fn is None:
        return False
    validated = any(
        isinstance(node, ast.ImportFrom)
        and node.module == "services.mpw_trx_email_recovery"
        and any(alias.name == "_posted_email" for alias in node.names)
        for node in ast.walk(fn)
    )
    binding = any(
        isinstance(node, (ast.Assign, ast.AnnAssign))
        and isinstance(node.value, ast.Name)
        and node.value.id == "submitted_email"
        and any(isinstance(target, ast.Attribute) and target.attr == "email"
                for target in (node.targets if isinstance(node, ast.Assign)
                               else [node.target]))
        for node in ast.walk(fn)
    )
    return validated and binding


def _no_synthetic_contact(tree):
    if tree is None:
        return False
    return not any(
        isinstance(node, ast.Constant) and isinstance(node.value, str)
        and "@guest.mojplaywin.invalid" in node.value
        for node in ast.walk(tree)
    )


def _recovery_contract(tree):
    return all(_function(tree, name) is not None
               for name in ("_posted_email", "bound_checkout"))


def _model_contract(tree):
    if tree is None:
        return False
    classes = {node.name for node in tree.body if isinstance(node, ast.ClassDef)}
    return {"GuestOrderEmail", "GuestRecoveryToken", "GuestRecoveryRate"} <= classes


def _migration_contract(tree):
    if tree is None:
        return False
    created = set()
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and
                isinstance(node.func, ast.Attribute) and
                node.func.attr == "CreateModel"):
            continue
        created.update(
            keyword.value.value for keyword in node.keywords
            if keyword.arg == "name"
            and isinstance(keyword.value, ast.Constant)
            and isinstance(keyword.value.value, str)
        )
    return {"GuestOrderEmail", "GuestRecoveryToken", "GuestRecoveryRate"} <= created


def _registration_contract(tree):
    if tree is None:
        return False
    return any(
        isinstance(node, ast.ImportFrom) and node.level == 1
        and node.module == "guest_recovery_models"
        and {"GuestOrderEmail", "GuestRecoveryToken", "GuestRecoveryRate"}
        <= {alias.name for alias in node.names}
        for node in tree.body
    )


def inspect(root: Path = ROOT) -> dict:
    trees = {name: _parse(root, relative) for name, relative in RELATIVE.items()}
    checks = {
        "invoice_post_email_binding_guard": _guarded_dispatch(trees["guest"]),
        "guest_principal_real_email_write": _guest_email_write(trees["guest"]),
        "no_synthetic_guest_contact": _no_synthetic_contact(trees["guest"]),
        "email_binding_and_recovery_module": _recovery_contract(trees["recovery"]),
        "immutable_order_claim_models": _model_contract(trees["models"]),
        "order_claim_migration_source": _migration_contract(trees["migration"]),
        "claim_model_registration": _registration_contract(trees["registration"]),
    }
    return {
        "schema": "mpw.guest_email_order_source_gate.v1",
        "source_checks": checks,
        "source_checks_passed": sum(checks.values()),
        "source_checks_total": len(checks),
        "source_candidate_complete": all(checks.values()),
        "server_email_order_binding_verified": False,
        "migration_applied_verified": False,
        "passenger_runtime_verified": False,
        "independent_trx_finality_verified": False,
        "paid_delivery_verified": False,
        "commercial_revenue_verified": None,
        "production_release_permitted": False,
        "customer_data_read": False,
        "database_accessed": False,
        "external_network_requests": False,
        "files_modified": False,
    }


def main() -> int:
    report = inspect()
    print("MPW_GUEST_EMAIL_SOURCE_GATE=" +
          json.dumps(report, sort_keys=True, separators=(",", ":")))
    return 0 if report["source_candidate_complete"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
