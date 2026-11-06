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
CATALOG = APP / "services" / "mpw_trx_public_catalog.py"
WEB = APP / "services" / "mpw_trx_commercial_web.py"
CONTEXT = APP / "services" / "mpw_trx_commercial_context.py"
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


def _called_names(node):
    return sorted({n.func.id for n in ast.walk(node)
                   if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)})


def _if_shapes(function, focus):
    if function is None:
        return []
    result = []
    for statement in ast.walk(function):
        if not isinstance(statement, ast.If):
            continue
        called = _called_names(statement.test)
        if not set(focus).intersection(called):
            continue
        test = statement.test
        clauses = test.values if isinstance(test, ast.BoolOp) else [test]
        negated = sorted({clause.operand.func.id for clause in clauses
                          if isinstance(clause, ast.UnaryOp)
                          and isinstance(clause.op, ast.Not)
                          and isinstance(clause.operand, ast.Call)
                          and isinstance(clause.operand.func, ast.Name)})
        returns_false = any(isinstance(n, ast.Return)
                            and isinstance(n.value, ast.Constant)
                            and n.value.value is False
                            for n in statement.body)
        returns_none = any(isinstance(n, ast.Return)
                           and (n.value is None or isinstance(n.value, ast.Constant)
                                and n.value.value is None)
                           for n in statement.body)
        raises = any(isinstance(n, ast.Raise) for n in statement.body)
        result.append({"line": statement.lineno,
                       "test_type": type(test).__name__,
                       "or_condition": isinstance(test, ast.BoolOp)
                                       and isinstance(test.op, ast.Or),
                       "calls": sorted(set(called).intersection(focus)),
                       "negated_calls": sorted(set(negated).intersection(focus)),
                       "returns_false": returns_false,
                       "returns_none": returns_none,
                       "raises": raises})
    return result[:12]


def collect():
    if pwd.getpwuid(os.geteuid()).pw_name != EXPECTED_USER:
        raise RuntimeError("WRONG_HOST_USER")
    if any(x.is_symlink() or not x.is_dir() for x in (APP, DOCROOT, PAGES.parent)):
        raise RuntimeError("UNSAFE_ROOT_OR_PARENT")
    if PAGES.is_symlink() or not PAGES.is_file():
        raise RuntimeError("UNSAFE_OR_MISSING_PAGES_MODULE")
    if CATALOG.is_symlink() or not CATALOG.is_file():
        raise RuntimeError("UNSAFE_OR_MISSING_CATALOG_MODULE")
    if any(p.is_symlink() or not p.is_file() for p in (WEB, CONTEXT)):
        raise RuntimeError("UNSAFE_OR_MISSING_COMMERCIAL_MODULE")
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
    catalog_size = CATALOG.stat().st_size
    if not 0 < catalog_size <= MAX_BYTES:
        raise RuntimeError("UNEXPECTED_CATALOG_SIZE")
    catalog_raw = CATALOG.read_bytes()
    if len(catalog_raw) != catalog_size:
        raise RuntimeError("CATALOG_CHANGED_DURING_READ")
    catalog_tree = ast.parse(catalog_raw.decode("utf-8"), filename="<live-mpw-catalog>")
    commercial_trees = {}
    commercial_digests = {}
    for key, path in (("web", WEB), ("context", CONTEXT)):
        stat_size = path.stat().st_size
        if not 0 < stat_size <= MAX_BYTES:
            raise RuntimeError("UNEXPECTED_COMMERCIAL_SIZE:" + key)
        contents = path.read_bytes()
        if len(contents) != stat_size:
            raise RuntimeError("COMMERCIAL_CHANGED_DURING_READ:" + key)
        commercial_trees[key] = ast.parse(contents.decode("utf-8"), filename="<live-mpw-"+key+">")
        commercial_digests[key] = hashlib.sha256(contents).hexdigest()
    context_fn = next((n for n in commercial_trees["context"].body
                       if isinstance(n, ast.FunctionDef)
                       and n.name == "rights_cleared_for_sale"), None)
    web_fn = next((n for n in commercial_trees["web"].body
                   if isinstance(n, ast.FunctionDef)
                   and n.name == "_select_order"), None)
    rights_fields = {n.value for n in ast.walk(context_fn)
                     if isinstance(n, ast.Constant) and isinstance(n.value, str)} if context_fn else set()
    catalog_functions = {node.name: node for node in catalog_tree.body
                         if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    catalog_helper = catalog_functions.get("public_trx_product")
    sellable_local = catalog_functions.get("sellable_trx_product")
    sellable_imports = sorted({
        node.module for node in ast.walk(catalog_tree)
        if isinstance(node, ast.ImportFrom) and node.module
        and any(alias.name == "sellable_trx_product" for alias in node.names)
    })
    sellable_local_names = sorted({
        node.id for node in ast.walk(sellable_local)
        if isinstance(node, ast.Name)
    })[:45] if sellable_local else []
    # Inspect control flow rather than relying on mere identifier presence.
    # This is a bounded shape-only record; no original statements are emitted.
    sellable_guard_shape = []
    if sellable_local:
        for statement in sellable_local.body:
            if not isinstance(statement, ast.If):
                continue
            calls = [node for node in ast.walk(statement.test)
                     if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)]
            called = sorted({node.func.id for node in calls})
            returns_none = any(isinstance(node, ast.Return)
                               and isinstance(node.value, ast.Constant)
                               and node.value.value is None
                               for node in statement.body)
            returns_false = any(isinstance(node, ast.Return)
                                and isinstance(node.value, ast.Constant)
                                and node.value.value is False
                                for node in statement.body)
            sellable_guard_shape.append({
                "line": statement.lineno,
                "test_kind": type(statement.test).__name__,
                "calls_rights": "rights_cleared_for_sale" in called,
                "calls_eligible": "_eligible" in called,
                "returns_none": returns_none,
                "returns_false": returns_false,
                "has_else": bool(statement.orelse),
            })
    public_helper_return_calls = sorted({
        node.value.func.id for node in ast.walk(catalog_helper)
        if isinstance(node, ast.Return) and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
    }) if catalog_helper else []
    catalog_names = sorted({
        node.id for node in ast.walk(catalog_helper)
        if isinstance(node, ast.Name)
    })[:45] if catalog_helper else []
    functions = {node.name: node for node in tree.body
                 if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    checkout = functions.get("product_checkout")
    public_product_imports = sorted({
        node.module for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
        and any(alias.name == "public_trx_product" for alias in node.names)
    })
    public_helper = functions.get("public_trx_product")
    helper_calls = sorted({
        node.func.id for node in ast.walk(public_helper)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    })[:40] if public_helper else []
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
        "catalog_sha256": hashlib.sha256(catalog_raw).hexdigest(),
        "catalog_has_product_helper": catalog_helper is not None,
        "catalog_product_helper_names": catalog_names,
        "sellable_helper_is_local": sellable_local is not None,
        "sellable_helper_imports": sellable_imports,
        "sellable_local_names": sellable_local_names,
        "sellable_guard_shape": sellable_guard_shape[:16],
        "sellable_expected_guard_shape": _if_shapes(sellable_local, ("_eligible", "rights_cleared_for_sale")),
        "catalog_public_product_gate_shape": _if_shapes(catalog_helper, ("sellable_trx_product",)),
        "public_product_return_calls": public_helper_return_calls[:16],
        "context_sha256": commercial_digests["context"],
        "web_sha256": commercial_digests["web"],
        "rights_helper_local": context_fn is not None,
        "rights_metadata_field_flags": {key: key in rights_fields for key in (
            "rights_cleared", "publication_approved", "rights_asset_sha256",
            "rights_document_sha256", "sha256")},
        "web_select_order_present": web_fn is not None,
        "web_select_order_has_transaction": bool(web_fn) and any(
            isinstance(n, ast.With) for n in ast.walk(web_fn)),
        "web_select_order_rights_guard": _if_shapes(web_fn, ("rights_cleared_for_sale",)),
        "catalog_helper_mentions_rights": "rights_cleared_for_sale" in catalog_names,
        "catalog_helper_mentions_eligible": "_eligible" in catalog_names,
        "import_old_count": source.count(IMPORT_OLD),
        "import_new_count": source.count(IMPORT_NEW),
        "checkout_old_count": source.count(CHECKOUT_OLD),
        "checkout_new_count": source.count(CHECKOUT_NEW),
        "has_public_shop": "public_shop" in functions,
        "has_product_checkout": checkout is not None,
        "public_product_is_local_helper": public_helper is not None,
        "public_product_imports": public_product_imports,
        "public_product_local_helper_calls": helper_calls,
        "checkout_identifier_names": names,
        "checkout_product_if_structure": checks[:12],
    }


if __name__ == "__main__":
    print("MPW_RIGHTS_PAGES_READONLY=" + json.dumps(collect(), sort_keys=True))
