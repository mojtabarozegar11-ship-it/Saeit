#!/usr/bin/env python3
"""Fail-closed preservation gate for MojPlayWin payments and products.

Read-only Git comparison: never connects to payment services, changes product
data, mutates production, or exposes wallet details. A successful check proves
only SOURCE-CODE preservation, not the health of live external gateways or the
integrity of the live product database; those require separately verified
backups, before/after inventory fingerprints and non-paying smoke tests.
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
from pathlib import Path


PROTECTED_FILES = frozenset({
    "config/urls.py",
    "core/admin.py",
    "core/commerce_views.py",
    "core/models.py",
    "core/services_views.py",
    "core/views.py",
    "core/templates/core/store.html",
    "core/templates/base.html",
    "scripts/deploy_mojplaywin_branding.py",
    ".github/workflows/mojplaywin-main-deploy.yml",
})
PROTECTED_DIRS = (
    "core/migrations/",
    "payments/",
    "wallets/",
    "checkout/",
    "fulfillment/",
    "orders/",
    "products/",
    "media/",
    "staticfiles/",
)
PROTECTED_PRODUCTION_STEMS = (
    "payment", "gateway", "wallet", "invoice", "order",
    "checkout", "fulfillment", "entitlement", "license", "settlement",
    "payout", "transaction", "product_download", "webhook",
)
PRODUCT_VIEW_FUNCTIONS = ("store", "branded_store_dispatch")
PRODUCT_TEMPLATE_FIELDS = (
    "{% for product in products %}",
    "{{ product.title }}",
    "{{ product.text }}",
    "{{ product.category }}",
    "{{ product.url }}",
    "{% static product.image %}",
)


def run_git(*args: str) -> str:
    p = subprocess.run(["git", *args], check=True, capture_output=True, text=True)
    return p.stdout


def diff_paths(base: str, head: str) -> list[str]:
    # --name-only catches added, renamed, deleted, modified or type-changed files.
    return run_git("diff", "--name-only", "--find-renames", base, head, "--").splitlines()


def forbidden_path(path: str) -> bool:
    if path in PROTECTED_FILES or any(path.startswith(d) for d in PROTECTED_DIRS):
        return True
    if path.startswith(("core/tests/", "tests/", "scripts/")):
        # All scripts also have individual test coverage; don't categorically
        # forbid the nonmutating commerce freeze test or this very guard.
        return False
    name = Path(path).stem.lower()
    if path.startswith("core/") and path.endswith((".py", ".html", ".js")):
        return any(re.search(r"(^|_)"+re.escape(token)+r"(_|$)", name)
                   for token in PROTECTED_PRODUCTION_STEMS)
    return False


def products_from_source(source: str):
    tree = ast.parse(source)
    matching = [
        node for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "PRODUCTS" for t in node.targets)
    ]
    if len(matching) != 1:
        raise ValueError("Cannot establish exactly one static MojPlayWin PRODUCTS catalog.")
    products = ast.literal_eval(matching[0].value)
    if not isinstance(products, list):
        raise ValueError("Expected existing PRODUCTS list.")
    return products


def function_structure(source: str, name: str) -> str:
    tree = ast.parse(source)
    funcs = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name]
    if len(funcs) != 1:
        raise ValueError(f"Missing or ambiguous commerce dispatch function: {name}")
    return ast.dump(funcs[0], include_attributes=False)


def test_template_bindings(source: str) -> list[str]:
    return [field for field in PRODUCT_TEMPLATE_FIELDS if field not in source]


def review(base: str, head: str) -> dict:
    changed = diff_paths(base, head)
    errors = [f"protected_file_modified:{p}" for p in changed if forbidden_path(p)]
    base_views = run_git("show", f"{base}:core/mojplaywin_views.py")
    head_views = run_git("show", f"{head}:core/mojplaywin_views.py")
    original = products_from_source(base_views)
    revised = products_from_source(head_views)
    if original != revised:
        errors.append("product_catalog_identity_price_or_link_changed")
    for name in PRODUCT_VIEW_FUNCTIONS:
        if function_structure(base_views, name) != function_structure(head_views, name):
            errors.append("commerce_dispatch_modified:"+name)
    # The redesign may restyle the catalog, but it must never drop
    # existing content bindings or product URL ownership.
    revised_html = run_git("show", f"{head}:core/templates/mojplaywin/store.html")
    errors.extend("store_binding_removed:"+x for x in test_template_bindings(revised_html))
    return {
        "baseline_commit": base,
        "draft_commit": head,
        "safe_in_version_control": not errors,
        "changed_paths": len(changed),
        "protected_file_modifications": [p for p in changed if forbidden_path(p)],
        "catalog_items": len(original),
        "catalog_fields_and_links_exactly_preserved": original == revised,
        "commerce_dispatch_functions_unchanged": all(
            function_structure(base_views, fn) == function_structure(head_views, fn)
            for fn in PRODUCT_VIEW_FUNCTIONS),
        "server_payments_verified": False,
        "production_product_inventory_verified": False,
        "errors": errors,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--output", type=Path, default=Path("mojplaywin-commerce-freeze-report.json"))
    args = parser.parse_args()
    result = review(args.base, args.head)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print("MOJPLAYWIN_COMMERCE_FREEZE="+("PASS" if result["safe_in_version_control"] else "FAIL"))
    print(f"Protected code changes: {len(result['protected_file_modifications'])}")
    print(f"Catalog entries compared: {result['catalog_items']}")
    if result["errors"]:
        for error in result["errors"]:
            print("BLOCKER: "+error)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
