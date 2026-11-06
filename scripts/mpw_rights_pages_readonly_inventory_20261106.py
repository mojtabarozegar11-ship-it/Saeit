#!/usr/bin/env python3
"""Bounded, read-only structural evidence for the live MojPlayWin rights gate.

Prints no Python source, credentials, private orders, customer data, or tokens.
It never imports the live application and never changes the host filesystem.
"""

import ast
import hashlib
import json
import os
import pathlib
import pwd


APP = pathlib.Path("/home/zomorod2/Saeit-staging")
DOCROOT = pathlib.Path("/home/zomorod2/mojplaywin.com")
PAGES = APP / "services" / "mpw_trx_public_pages.py"
EXPECTED_USER = "zomorod2"
MAX_BYTES = 2_000_000

IMPORT_OLD = "from services.mpw_trx_walletless_core import PaymentHold\n"
IMPORT_NEW = IMPORT_OLD + (
    "from services.mpw_trx_commercial_context import rights_cleared_for_sale\n"
)
CHECKOUT_OLD = (
    "    if product is None or not _eligible(product): raise Http404\n"
)
CHECKOUT_NEW = (
    "    if product is None or not _eligible(product) "
    "or not rights_cleared_for_sale(product):\n"
    "        raise Http404\n"
)


def collect():
    if pwd.getpwuid(os.geteuid()).pw_name != EXPECTED_USER:
        raise RuntimeError("WRONG_HOST_USER")
    if any(x.is_symlink() or not x.is_dir() for x in (APP, DOCROOT, PAGES.parent)):
        raise RuntimeError("UNSAFE_ROOT_OR_PARENT")
    if PAGES.is_symlink() or not PAGES.is_file():
        raise RuntimeError("UNSAFE_OR_MISSING_PAGES_MODULE")
    wsgi = DOCROOT / "passenger_wsgi.py"
    if wsgi.is_symlink() or not wsgi.is_file():
        raise RuntimeError("UNSAFE_OR_MISSING_WSGI")
    if b"Saeit-staging" not in wsgi.read_bytes():
        raise RuntimeError("UNEXPECTED_PASSENGER_MAPPING")

    size = PAGES.stat().st_size
    if not 0 < size <= MAX_BYTES:
        raise RuntimeError("UNEXPECTED_PAGES_SIZE")
    raw = PAGES.read_bytes()
    if len(raw) != size:
        raise RuntimeError("PAGES_CHANGED_DURING_READ")
    source = raw.decode("utf-8")
    tree = ast.parse(source, filename="<live-mpw-pages>")
    functions = {node.name: node for node in tree.body
                 if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    checkout = functions.get("product_checkout")
    public_product_imports = sorted({
        node.module for node in tree.body
        if isinstance(node, ast.ImportFrom) and node.module
        and any(alias.name == "public_trx_product" for alias in node.names)
    })
    names = sorted({node.id for node in ast.walk(checkout)
                    if isinstance(node, ast.Name)})[:50] if checkout else []
    checks = []
    if checkout:
        for node in ast.walk(checkout):
            if isinstance(node, ast.If):
                identifiers = {value.id for value in ast.walk(node.test)
                               if isinstance(value, ast.Name)}
                if "product" in identifiers:
                    product_is_none = (
                        isinstance(node.test, ast.Compare)
                        and isinstance(node.test.left, ast.Name)
                        and node.test.left.id == "product"
                        and len(node.test.ops) == 1
                        and isinstance(node.test.ops[0], ast.Is)
                        and len(node.test.comparators) == 1
                        and isinstance(node.test.comparators[0], ast.Constant)
                        and node.test.comparators[0].value is None
                    )
                    raises_404 = any(
                        isinstance(value, ast.Raise)
                        and (
                            isinstance(value.exc, ast.Name)
                            and value.exc.id == "Http404"
                            or isinstance(value.exc, ast.Call)
                            and isinstance(value.exc.func, ast.Name)
                            and value.exc.func.id == "Http404"
                        )
                        for value in node.body
                    )
                    checks.append({"line": node.lineno,
                                   "kind": type(node.test).__name__,
                                   "line_span": node.end_lineno-node.lineno+1,
                                   "exact_product_is_none": product_is_none,
                                   "raises_http404": raises_404,
                                   "mentions_eligible": "_eligible" in identifiers,
                                   "mentions_rights": "rights_cleared_for_sale" in identifiers})

    return {
        "read_only": True,
        "no_source_or_customer_data": True,
        "pages_sha256": hashlib.sha256(raw).hexdigest(),
        "pages_size": size,
        "import_old_count": source.count(IMPORT_OLD),
        "import_new_count": source.count(IMPORT_NEW),
        "checkout_old_count": source.count(CHECKOUT_OLD),
        "checkout_new_count": source.count(CHECKOUT_NEW),
        "has_public_shop": "public_shop" in functions,
        "has_product_checkout": checkout is not None,
        "public_product_imports": public_product_imports,
        "checkout_identifier_names": names,
        "checkout_product_if_structure": checks[:12],
    }


if __name__ == "__main__":
    print("MPW_RIGHTS_PAGES_READONLY=" + json.dumps(collect(), sort_keys=True))
