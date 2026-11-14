#!/usr/bin/env python3
"""Read-only source reconciliation for MojPlayWin's buyer-email guest checkout.

Intended for the existing ONE organization identity mojtaba.bot.ai.
No database, Django import, HTTP call, key access, invoice, payment or mutation.
Source checks cannot certify Passenger origins or paid customer delivery.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path
import stat

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    "guest": "services/mpw_trx_guest_commerce.py",
    "recovery": "services/mpw_trx_email_recovery.py",
    "claims": "core/guest_recovery_models.py",
    "migration": "core/migrations/0049_mpw_guest_email_recovery.py",
    "registration": "core/models.py",
    "render": "services/mpw_checkout_render_contract.py",
}
MAX_BYTES = 240_000


def _load(root, relative):
    """Bounded, regular, non-symlink app file. Never leaks its contents."""
    if type(root) is not Path or root.is_symlink() or not root.is_dir():
        return None
    path = root
    for element in Path(relative).parts:
        if element in (".", "..", ""):
            return None
        path = path / element
        if path.is_symlink():
            return None
    try:
        info = path.stat()
        if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= MAX_BYTES:
            return None
        raw = path.read_bytes()
        if len(raw) != info.st_size:
            return None
        return ast.parse(raw.decode("utf-8"))
    except (OSError, UnicodeError, ValueError, SyntaxError, RecursionError):
        return None


def _one(tree, name):
    if tree is None:
        return None
    found = [node for node in tree.body if isinstance(node, ast.FunctionDef)
             and node.name == name]
    return found[0] if len(found) == 1 else None


def _call(node, target):
    """Qualified exact call target, not arbitrary matching literal text."""
    if node is None:
        return False
    for item in ast.walk(node):
        if not isinstance(item, ast.Call):
            continue
        parts = []
        member = item.func
        while isinstance(member, ast.Attribute):
            parts.append(member.attr)
            member = member.value
        if isinstance(member, ast.Name):
            parts.append(member.id)
        if ".".join(reversed(parts)) == target:
            return True
    return False


def _assignment(node, attribute, name=None, value=None):
    if node is None:
        return False
    for item in ast.walk(node):
        if not isinstance(item, (ast.Assign, ast.AnnAssign)):
            continue
        targets = item.targets if isinstance(item, ast.Assign) else [item.target]
        for target in targets:
            if not (isinstance(target, ast.Attribute)
                    and target.attr == attribute
                    and isinstance(target.value, ast.Name)
                    and (name is None or target.value.id == name)):
                continue
            expr = item.value
            if value is None:
                return True
            if isinstance(expr, ast.Name) and expr.id == value:
                return True
            if isinstance(expr, ast.Constant) and expr.value is value:
                return True
    return False


def _call_keyword(node, target, keyword, expected):
    if node is None:
        return False
    for call in ast.walk(node):
        if not isinstance(call, ast.Call):
            continue
        try:
            text = ast.unparse(call.func)
        except (ValueError, TypeError, RecursionError):
            continue
        if text != target:
            continue
        for item in call.keywords:
            if item.arg == keyword and isinstance(item.value, ast.Constant) \
                    and item.value.value is expected:
                return True
    return False


def _import(tree, module, member):
    if tree is None:
        return False
    return any(
        isinstance(node, ast.ImportFrom) and node.level == 0
        and node.module == module
        and any(alias.name == member for alias in node.names)
        for node in ast.walk(tree)
    )


def _model_names(tree):
    if tree is None:
        return set()
    return {node.name for node in tree.body if isinstance(node, ast.ClassDef)}


def _migration_names(tree):
    if tree is None:
        return set()
    result = set()
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "CreateModel"):
            continue
        for item in node.keywords:
            if item.arg == "name" and isinstance(item.value, ast.Constant) \
                    and isinstance(item.value.value, str):
                result.add(item.value.value)
    return result


def _has_raise_string(node, value):
    if node is None:
        return False
    return any(isinstance(item, ast.Constant) and item.value == value
               for item in ast.walk(node))


def inspect(root: Path = ROOT) -> dict:
    """Check exact safety/dependency evidence; never change any system."""
    trees = {name: _load(root, path) for name, path in SOURCES.items()}
    g, r = trees["guest"], trees["recovery"]
    guest_user, dispatch = _one(g, "_new_user"), _one(g, "_dispatch")
    install_cookie = _one(g, "_install_cookie")
    bound = _one(r, "bound_checkout")
    eligible, ready, download = (_one(r, "_eligible_orders"),
                                 _one(r, "_ready"),
                                 _one(r, "recovery_download"))
    model_types = {"GuestOrderEmail", "GuestRecoveryToken", "GuestRecoveryRate"}
    checks = {
        # File source is necessary, never sufficient, for production approval.
        "guest_source": g is not None,
        "recovery_source": r is not None,
        "claim_models_source": trees["claims"] is not None,
        "migration_source": trees["migration"] is not None,
        "registration_source": trees["registration"] is not None,
        "render_contract_source": trees["render"] is not None,
        "guest_constructor_unique": guest_user is not None,
        "guest_validated_email_import": _import(g, "services.mpw_trx_email_recovery", "_posted_email"),
        "guest_validated_email_call": _call(guest_user, "_posted_email"),
        "guest_email_assignment": _assignment(guest_user, "email", "user", "submitted_email"),
        "guest_account_force_insert": _call_keyword(guest_user, "user.save", "force_insert", True),
        "guest_unusable_password": _call(guest_user, "user.set_unusable_password"),
        "guest_staff_denied": _assignment(guest_user, "is_staff", "user", False),
        "guest_superuser_denied": _assignment(guest_user, "is_superuser", "user", False),
        "guest_identity_conflict_denied": _has_raise_string(guest_user, "Guest buyer email identity conflict"),
        "guest_signed_cookie": _call(guest_user, "signing.dumps"),
        "guest_cookie_secure": _call_keyword(install_cookie, "response.set_cookie", "secure", True),
        "guest_cookie_httponly": _call_keyword(install_cookie, "response.set_cookie", "httponly", True),
        "guest_host_validator_present": _one(g, "_host_ok") is not None,
        "guest_dispatch_unique": dispatch is not None,
        "guest_order_bound_checkout_import": _import(dispatch, "services.mpw_trx_email_recovery", "bound_checkout"),
        "guest_order_bound_checkout_call": _call(dispatch, "bound_checkout"),
        "guest_checkout_render_guard": _call(_one(g, "_checkout_page"), "require_checkout_markup"),
        "recovery_posted_email_unique": _one(r, "_posted_email") is not None,
        "recovery_validates_email": _call(_one(r, "_email"), "validate_email"),
        "recovery_bound_checkout_unique": bound is not None,
        "recovery_order_transaction": _call(bound, "transaction.atomic"),
        "recovery_order_claim_creation": _call(bound, "GuestOrderEmail.objects.create"),
        "recovery_signal_connect": _call(bound, "post_save.connect"),
        "recovery_signal_disconnect": _call(bound, "post_save.disconnect"),
        "recovery_invoice_fullmatch": _call(bound, "INVOICE_RE.fullmatch"),
        "recovery_signed_digest": _call(_one(r, "_digest"), "hmac.new"),
        "recovery_all_items_ready": _call(ready, "OrderItem.objects.filter") and _call(ready, "ready.values"),
        "recovery_finality_on_access": _call(eligible, "verified_walletless_credit")
                                       and _call(download, "verified_walletless_credit"),
        "recovery_delivery_guard": _call(download, "_ready"),
        "claim_model_trio": model_types.issubset(_model_names(trees["claims"])),
        "migration_model_trio": model_types.issubset(_migration_names(trees["migration"])),
        "registered_claim_model": _import(trees["registration"], "guest_recovery_models", "GuestOrderEmail")
                                  or any(isinstance(n, ast.ImportFrom) and n.level == 1
                                         and n.module == "guest_recovery_models"
                                         and {"GuestOrderEmail", "GuestRecoveryToken", "GuestRecoveryRate"}
                                         <= {a.name for a in n.names}
                                         for n in (trees["registration"].body if trees["registration"] else [])),
        "render_contract_function": _one(trees["render"], "checkout_markup_category") is not None
                                    and _one(trees["render"], "require_checkout_markup") is not None,
    }
    return {
        "schema": "mojtaba.bot.ai.mpw-email-required-source-preflight.v1",
        "canonical_bot": "mojtaba.bot.ai",
        "checks": checks,
        "passed": sum(checks.values()),
        "total": len(checks),
        "source_candidate_complete": all(checks.values()),
        "must_still_verify_applied_migration": True,
        "effective_passenger_root_verified": False,
        "effective_checkout_template_verified": False,
        "public_store_dynamic_verified": False,
        "checkout_security_headers_verified": False,
        "real_guest_post_order_verified": False,
        "settled_payment_verified": False,
        "paid_delivery_verified": False,
        "release_authorized": False,
        "actual_collected_revenue": None,
        "external_network_requests": False,
        "database_queries": False,
        "customer_data_read": False,
        "files_modified": False,
    }


def require_source(root: Path = ROOT) -> dict:
    report = inspect(root)
    if not report["source_candidate_complete"]:
        # Fixed error, never echo paths, secrets or source/customer details.
        raise RuntimeError("EMAIL_REQUIRED_SOURCE_CONTRACT_NOT_PROVEN")
    return report


if __name__ == "__main__":
    report = inspect()
    print("MPW_EMAIL_REQUIRED_SOURCE=" + json.dumps(report, sort_keys=True, separators=(",", ":")))
    raise SystemExit(0 if report["source_candidate_complete"] else 2)
