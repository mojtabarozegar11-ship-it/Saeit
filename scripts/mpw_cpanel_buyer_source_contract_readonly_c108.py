#!/usr/bin/env python3
"""Fixed-field, owner-only, read-only AST hints for existing staging checkout.

This intentionally does NOT import app source, execute Django, inspect
settings/environment, connect to DB, access customer data, call TRON nodes,
create files, alter site state, or print original code or source hashes.
Observed syntax/call tokens are NOT proof of operational paid fulfillment.
"""
import ast
import json
import os
from pathlib import Path
import stat

ROOT = Path("/home/zomorod2/Saeit-staging")
LIMIT = 262144
FILES = {
    "mpw_commerce/checkout_views.py": (
        "checkout_challenge", "checkout_verify_signature",
        "checkout_invoice", "checkout_status"),
    "mpw_commerce/product_checkout_page.py": ("product_checkout_page",),
    "mpw_commerce/purchase_history.py": ("purchased_downloads",),
    "mpw_commerce/customer_auth.py": (
        "CustomerLogin", "CustomerLogout", "customer_register"),
    "mpw_commerce/buyer_orders.py": ("create_digital_order",),
    "mpw_commerce/policy.py": ("order_snapshot", "CommercePolicyError"),
    "mpw_commerce/entitlements.py": ("can_access_purchased_digital_item",),
    "mpw_commerce/downloads.py": ("download_paid_item",),
    "mpw_commerce/urls.py": ("urlpatterns",),
    "gateway_contract/merchant_binding.py": ("resolve_registered_merchant",),
    "mpw_native_checkout/wallet_ownership.py": ("proven_merchant_wallets",),
    "services/mpw_trx_commercial_web.py": (),
    "services/mpw_trx_public_pages.py": (),
}
PREFIX = "MPW_LIVE_BUYER_SOURCE_AST_READONLY="
_SIGNAL_NAMES = (
    "source_checkout_handlers_defined",
    "source_customer_auth_exports_defined",
    "source_buyer_order_handler_defined",
    "source_buyer_cart_scope_helper_defined",
    "source_buyer_email_check_helper_defined",
    "source_paid_download_invokes_entitlement",
    "source_paid_entitlement_invokes_receipt_scope",
    "source_merchant_binding_resolver_defined",
    "source_wallet_proven_merchant_adapter_defined",
    "source_checkout_order_route_literal",
    "source_paid_file_route_literal",
)


def _read_fixed(root, relative):
    """Return bytes under approved root via descriptor-anchored no-symlink walk."""
    descriptors = []
    try:
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        descriptors.append(os.open(root, flags))
        parts = Path(relative).parts
        if not parts or any(x in (".", "..") for x in parts):
            return None
        for segment in parts[:-1]:
            descriptors.append(os.open(segment, flags, dir_fd=descriptors[-1]))
        fd = os.open(parts[-1],
                     os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                     dir_fd=descriptors[-1])
        descriptors.append(fd)
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_size > LIMIT:
            return None
        data = os.read(fd, LIMIT + 1)
        return data if len(data) <= LIMIT and len(data) == st.st_size else None
    except (OSError, ValueError):
        return None
    finally:
        for d in reversed(descriptors):
            os.close(d)


def _export_names(tree):
    found = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            found.add(node.name)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    found.add(t.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            found.add(node.target.id)
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name != "*":
                    found.add(alias.asname or alias.name)
    return found


def _function(tree, name):
    if tree is None:
        return None
    return next((n for n in tree.body
                 if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                 and n.name == name), None)


def _direct_call(fn, name):
    if fn is None:
        return False
    return any(
        isinstance(n, ast.Call) and (
            (isinstance(n.func, ast.Name) and n.func.id == name) or
            (isinstance(n.func, ast.Attribute) and n.func.attr == name))
        for n in ast.walk(fn)
    )


def _source_literal(tree, val):
    if tree is None:
        return False
    return any(isinstance(n, ast.Constant) and n.value == val
               for n in ast.walk(tree))


def inspect(root=ROOT):
    report = {
        "schema": "mpw.cpanel.buyer-source-ast.readonly.v1",
        "read_only": True,
        "root_valid": False,
        "application_imported": False,
        "customer_data_read": False,
        "database_read": False,
        "network_used": False,
        "files_modified": False,
        "release_permitted": False,
        "payment_proven": False,
        "runtime_passenger_proven": False,
        "module_states": {
            p: {"present": False, "parseable": False,
                "exports_present": False} for p in FILES
        },
        "source_signals": {name: False for name in _SIGNAL_NAMES},
    }
    try:
        if ((root != ROOT and root.name != "fixture_checkout_root") or
                root.is_symlink() or not root.is_dir() or
                root.resolve(strict=True) != root):
            return report
        report["root_valid"] = True
        trees = {}
        for p, exports in FILES.items():
            raw = _read_fixed(root, p)
            if raw is None:
                continue
            state = report["module_states"][p]
            state["present"] = True
            try:
                tree = ast.parse(raw.decode("utf-8"), filename=p)
                state["parseable"] = True
                state["exports_present"] = all(x in _export_names(tree)
                                               for x in exports)
                trees[p] = tree
            except (SyntaxError, UnicodeError, ValueError):
                pass

        checkout = trees.get("mpw_commerce/checkout_views.py")
        auth = trees.get("mpw_commerce/customer_auth.py")
        buyer = trees.get("mpw_commerce/buyer_orders.py")
        download = trees.get("mpw_commerce/downloads.py")
        rights = trees.get("mpw_commerce/entitlements.py")
        merchant = trees.get("gateway_contract/merchant_binding.py")
        wallet = trees.get("mpw_native_checkout/wallet_ownership.py")
        urls = trees.get("mpw_commerce/urls.py")
        report["source_signals"] = {
            "source_checkout_handlers_defined": (
                checkout is not None and all(
                    _function(checkout, name) is not None
                    for name in FILES["mpw_commerce/checkout_views.py"])),
            "source_customer_auth_exports_defined": (
                auth is not None and all(
                    n in _export_names(auth)
                    for n in FILES["mpw_commerce/customer_auth.py"])),
            "source_buyer_order_handler_defined":
                _function(buyer, "create_digital_order") is not None,
            "source_buyer_cart_scope_helper_defined":
                _function(buyer, "_cart_scope_matches") is not None,
            "source_buyer_email_check_helper_defined":
                _function(buyer, "_buyer_has_valid_email") is not None,
            "source_paid_download_invokes_entitlement":
                _direct_call(_function(download, "download_paid_item"),
                             "can_access_purchased_digital_item"),
            "source_paid_entitlement_invokes_receipt_scope":
                _direct_call(
                    _function(rights, "can_access_purchased_digital_item"),
                    "require_persisted_receipt_scope"),
            "source_merchant_binding_resolver_defined":
                _function(merchant, "resolve_registered_merchant") is not None,
            "source_wallet_proven_merchant_adapter_defined":
                _function(wallet, "proven_merchant_wallets") is not None,
            "source_checkout_order_route_literal":
                _source_literal(urls, "commerce/checkout/order/"),
            "source_paid_file_route_literal":
                _source_literal(urls, "commerce/download/<int:item_id>/"),
        }
    except (OSError, ValueError):
        report["root_valid"] = False
    return report


def main():
    print(PREFIX + json.dumps(inspect(), sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
