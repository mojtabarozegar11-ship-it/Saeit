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
    "mpw_commerce/buyer_orders.py",
    "mpw_commerce/buyer_wallets.py",
    "mpw_commerce/invoicing.py",
    "mpw_commerce/entitlements.py",
    "mpw_commerce/policy.py",
    "mpw_commerce/settlement.py",
    "core/migrations/0049_mpw_guest_email_recovery.py",
)


def _app_registered(settings_source: str) -> bool:
    """Recognize only unconditional top-level INSTALLED_APPS declarations."""
    try:
        tree = ast.parse(settings_source, filename="config/settings.py")
    except SyntaxError:
        return False

    def contains_app(node: ast.AST) -> bool:
        return any(isinstance(child, ast.Constant) and child.value in (
            "mpw_commerce", "mpw_commerce.apps.MpwCommerceConfig"
        ) for child in ast.walk(node))

    # A conditional append is not evidence that the app is installed now.
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(isinstance(t, ast.Name) and t.id == "INSTALLED_APPS" for t in targets):
                if node.value is not None and contains_app(node.value):
                    return True
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if (node.func.attr == "append" and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "INSTALLED_APPS" and node.args
                    and contains_app(node.args[0])):
                return True
    return False


def inspect(root: Path) -> dict:
    """Return source-only evidence. No actual release approval is computed."""
    inventory = []
    for relative in REQUIRED:
        path = root / relative
        exists = path.is_file() and not path.is_symlink()
        item = {"path": relative, "present": exists}
        if exists:
            item["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        inventory.append(item)

    settings_path = root / "config/settings.py"
    settings_present = settings_path.is_file() and not settings_path.is_symlink()
    registered = False
    if settings_present:
        try:
            registered = _app_registered(settings_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError):
            registered = False

    found = sum(item["present"] for item in inventory)
    return {
        "kind": "mpw_guest_recovery_source_preflight_v1",
        "required_count": len(inventory),
        "present_count": found,
        "missing": [item["path"] for item in inventory if not item["present"]],
        "mpw_commerce_registered_in_settings_source": registered,
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
