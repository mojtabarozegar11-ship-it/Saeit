"""Read-only source closure gate for MojPlayWin guest recovery and TRX delivery.

Run against the *verified* intended application source root. This never imports
the application, queries a database, changes a file, or authorizes deployment.
Passing source checks is not evidence of a paid production purchase.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path


# Known direct and second-level dependencies from both legacy source branches.
# The list is a floor, not a proof that the entire dynamic import graph is closed.
REQUIRED = (
    "services/mpw_trx_email_recovery.py",
    "services/mpw_trx_guest_commerce.py",
    "services/mpw_trx_public_pages.py",
    "services/mpw_trx_commercial_web.py",
    "services/mpw_trx_commercial_context.py",
    "services/mpw_trx_walletless_core.py",
    "services/mpw_trx_walletless_one_tap_ui.py",
    "services/mpw_trx_walletless_checkout_ui.py",
    "services/mpw_walletless_commercial_intent.py",
    "services/mpw_walletless_django_test_bridge.py",
    "services/mpw_tron_readonly_deposit_candidates.py",
    "services/mpw_tron_independent_solidified_rpc.py",
    "services/mpw_trx_commercial_chain.py",
    "mpw_commerce/__init__.py",
    "mpw_commerce/apps.py",
    "mpw_commerce/models.py",
    "mpw_commerce/migrations/0001_initial.py",
    "mpw_commerce/downloads.py",
    "mpw_commerce/templates/mpw_commerce/product_checkout.html",
    "mpw_commerce/buyer_orders.py",
    "mpw_commerce/buyer_wallets.py",
    "mpw_commerce/invoicing.py",
    "mpw_commerce/entitlements.py",
    "mpw_commerce/policy.py",
    "mpw_commerce/settlement.py",
    "core/migrations/0049_mpw_guest_email_recovery.py",
)


MAX_SOURCE_BYTES = 800_000


def _read_bounded_source(root: Path, relative: str):
    """Fixed relative paths only; reject symlink components and large files.

    The verified root itself must be trusted. This is a source metadata gate,
    not a substitute for process identity, migration or runtime attestation.
    """
    current = root
    if current.is_symlink():
        return None, "symlink"
    for part in Path(relative).parts:
        if part in (".", "..") or not part:
            return None, "invalid_path"
        current = current / part
        if current.is_symlink():
            return None, "symlink"
    try:
        if not current.is_file():
            return None, "missing"
        if current.stat().st_size > MAX_SOURCE_BYTES:
            return None, "too_large"
        with current.open("rb") as source:
            data = source.read(MAX_SOURCE_BYTES + 1)
        if len(data) > MAX_SOURCE_BYTES:
            return None, "too_large"
        return data, None
    except OSError:
        return None, "unreadable"


def _app_registered(settings_source: str) -> bool:
    """Accept only literal unconditional INSTALLED_APPS membership.

    Dynamic expressions and conditional branches are unproven, not enabled.
    """
    try:
        tree = ast.parse(settings_source, filename="config/settings.py")
    except SyntaxError:
        return False

    app_names = ("mpw_commerce", "mpw_commerce.apps.MpwCommerceConfig")

    def is_app(node):
        return isinstance(node, ast.Constant) and node.value in app_names

    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(isinstance(t, ast.Name) and t.id == "INSTALLED_APPS" for t in targets):
                value = node.value
                if isinstance(value, (ast.List, ast.Tuple)) and any(
                    is_app(entry) for entry in value.elts
                ):
                    return True
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            call = node.value
            if (isinstance(call.func, ast.Attribute) and call.func.attr == "append"
                    and isinstance(call.func.value, ast.Name)
                    and call.func.value.id == "INSTALLED_APPS"
                    and len(call.args) == 1 and not call.keywords
                    and is_app(call.args[0])):
                return True
    return False


def inspect(root: Path) -> dict:
    """Return source-only evidence. No actual release approval is computed."""
    inventory = []
    for relative in REQUIRED:
        payload, issue = _read_bounded_source(root, relative)
        item = {"path": relative, "present": payload is not None}
        if payload is not None:
            item["sha256"] = hashlib.sha256(payload).hexdigest()
        elif issue != "missing":
            item["issue"] = issue
        inventory.append(item)

    settings_payload, settings_issue = _read_bounded_source(root, "config/settings.py")
    registered = False
    if settings_payload is not None:
        try:
            registered = _app_registered(settings_payload.decode("utf-8"))
        except UnicodeError:
            registered = False

    found = sum(item["present"] for item in inventory)
    return {
        "kind": "mpw_guest_recovery_source_preflight_v1",
        "required_count": len(inventory),
        "present_count": found,
        "missing": [item["path"] for item in inventory if not item["present"]],
        "mpw_commerce_registered_in_settings_source": registered,
        "settings_source_issue": settings_issue if settings_issue != "missing" else None,
        "source_floor_pass": found == len(inventory) and registered,
        "inventory": inventory,
        "database_schema_verified": False,
        "production_runtime_verified": False,
        "off_host_restore_verified": False,
        "live_paid_delivery_verified": False,
        "release_permitted": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True,
                        help="Explicit, verified source root; never infer production root")
    args = parser.parse_args()
    if not args.root.is_dir() or args.root.is_symlink():
        parser.error("--root must name an existing non-symlink directory")
    result = inspect(args.root)
    print(json.dumps(result, sort_keys=True, ensure_ascii=False, indent=2))
    return 0 if result["source_floor_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
