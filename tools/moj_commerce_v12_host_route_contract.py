#!/usr/bin/env python3
"""Static, write-free host route compatibility preflight for MOJ Commerce v1.2.

Inspects tracked source as DATA; never imports the live settings, touches the
production database, opens a web endpoint, or mounts a new route.
"""
import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {
    "moj-commerce-merchant-console",
    "moj-commerce-merchant-dashboard",
    "moj-commerce-operator-scanner-health",
    "moj-commerce-buyer-checkout",
    "moj-commerce-checkout-status",
    "moj-commerce-wallet-challenge",
    "moj-commerce-wallet-verify",
    "moj-commerce-tron-fulfill",
    "moj-commerce-download-link",
    "moj-commerce-download",
}
CONVERTERS = {
    "str": r"[^/]+",
    "int": r"[0-9]+",
    "slug": r"[-a-zA-Z0-9_]+",
    "uuid": r"[0-9a-fA-F-]{36}",
    "path": r".+",
}
EXAMPLE = {
    "str": "order123",
    "int": "1",
    "slug": "demo",
    "uuid": "12345678-1234-1234-1234-123456789abc",
    "path": "sample/path",
}
VARIABLE = re.compile(r"<(?:(str|int|slug|uuid|path):)?([a-zA-Z_][a-zA-Z_0-9]*)>")


def _read_source(path):
    source = ROOT / path
    if source.is_symlink() or not source.is_file():
        raise ValueError("missing_or_linked_source")
    return ast.parse(source.read_text("utf-8"), filename=path)


def _calls(tree):
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
            continue
        if node.func.id != "path" or len(node.args) < 2:
            continue
        route = node.args[0]
        if not isinstance(route, ast.Constant) or not isinstance(route.value, str):
            raise ValueError("non_literal_route")
        name = None
        for kw in node.keywords:
            if kw.arg == "name" and isinstance(kw.value, ast.Constant):
                name = kw.value.value
        include_module = None
        target = node.args[1]
        if isinstance(target, ast.Call) and isinstance(target.func, ast.Name) and target.func.id == "include":
            if target.args and isinstance(target.args[0], ast.Constant):
                include_module = target.args[0].value
        found.append((route.value, name, include_module))
    return found


def _example(route):
    return VARIABLE.sub(lambda m: EXAMPLE[m.group(1) or "str"], route)


def _matches(route, candidate):
    chunks = []
    offset = 0
    for m in VARIABLE.finditer(route):
        chunks.append(re.escape(route[offset:m.start()]))
        chunks.append("(?:%s)" % CONVERTERS[m.group(1) or "str"])
        offset = m.end()
    chunks.append(re.escape(route[offset:]))
    return re.fullmatch("".join(chunks), candidate) is not None


def _installed_apps(settings_tree):
    for node in settings_tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "INSTALLED_APPS" for t in node.targets
        ):
            if not isinstance(node.value, ast.List):
                raise ValueError("dynamic_installed_apps")
            apps = []
            for value in node.value.elts:
                if not isinstance(value, ast.Constant) or not isinstance(value.value, str):
                    raise ValueError("dynamic_installed_apps")
                apps.append(value.value)
            return apps
    raise ValueError("missing_installed_apps")


def audit():
    host = _calls(_read_source("config/urls.py"))
    core = _calls(_read_source("core/urls.py"))
    commerce = _calls(_read_source("moj_commerce/urls.py"))
    installed = _installed_apps(_read_source("config/settings.py"))

    # This stage must not silently turn on the payment surface in production.
    if any("moj_commerce" in name for name in installed):
        raise ValueError("production_app_already_installed_requires_runtime_audit")
    if any("moj_commerce" in (include or "") for _, _, include in host):
        raise ValueError("production_route_already_mounted_requires_runtime_audit")

    host_paths = [route for route, _, included in host if included is None]
    if not any(route == "api/" and included == "core.urls" for route, _, included in host):
        raise ValueError("unknown_host_api_mount")
    host_paths.extend("api/" + route for route, _, included in core if included is None)

    route_names = [name for _, name, _ in commerce]
    if len(set(route_names)) != len(route_names) or set(route_names) != EXPECTED:
        raise ValueError("commerce_routes_incomplete_or_duplicate")
    candidates = [_example(route) for route, _, include in commerce if include is None]
    if len(candidates) != len(commerce):
        raise ValueError("commerce_nested_include_requires_review")
    collisions = sum(_matches(route, candidate) for route in host_paths for candidate in candidates)
    if collisions:
        raise ValueError("commerce_route_shadowed_by_existing_host")
    return {
        "classification": "MOJ_COMMERCE_V12_STATIC_HOST_ROUTE_CONTRACT",
        "existing_root_routes_examined": len(host),
        "existing_api_routes_examined": len(core),
        "commerce_routes_examined": len(commerce),
        "route_collisions": 0,
        "commerce_mounted_on_existing_host": False,
        "commerce_installed_in_existing_host": False,
        "production_writes": False,
        "database_access": False,
        "release_permitted": False,
    }


def selftest():
    assert _matches("store/<int:product_id>/", "store/7/")
    assert not _matches("store/<int:product_id>/", "store/text/")
    assert _matches("blog/<path:slug>/", "blog/some/path/")
    assert not _matches("blog/<path:slug>/", "moj-commerce/orders/x/status/")
    assert _example("orders/<uuid:id>/") == "orders/12345678-1234-1234-1234-123456789abc/"


if __name__ == "__main__":
    try:
        selftest()
        report = audit()
        print(json.dumps(report, sort_keys=True))
    except Exception:
        print(json.dumps({
            "classification": "MOJ_COMMERCE_V12_HOST_ROUTE_CONTRACT_BLOCKED",
            "error": "STRUCTURAL_COMPATIBILITY_NOT_PROVEN",
            "release_permitted": False,
        }, sort_keys=True))
        sys.exit(1)
