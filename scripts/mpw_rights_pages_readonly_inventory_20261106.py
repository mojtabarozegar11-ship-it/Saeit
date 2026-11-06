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
    names = sorted({node.id for node in ast.walk(checkout)
                    if isinstance(node, ast.Name)})[:50] if checkout else []
    checks = []
    if checkout:
        for node in ast.walk(checkout):
            if isinstance(node, ast.If):
                identifiers = {value.id for value in ast.walk(node.test)
                               if isinstance(value, ast.Name)}
                if "product" in identifiers:
                    checks.append({"line": node.lineno,
                                   "kind": type(node.test).__name__,
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
        "checkout_identifier_names": names,
        "checkout_product_if_structure": checks[:12],
    }


if __name__ == "__main__":
    print("MPW_RIGHTS_PAGES_READONLY=" + json.dumps(collect(), sort_keys=True))
