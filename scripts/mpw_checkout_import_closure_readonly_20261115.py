#!/usr/bin/env python3
"""Inspect cPanel's deployed checkout Python import closure WITHOUT importing it.

Uses only Python AST and bounded source reads. Does not touch DB, payments,
wallets, email, HTTP, package import machinery, or server files beyond reads.
Run under the owner-approved read-only SSH identity and PYTHONDONTWRITEBYTECODE.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

APP_ROOT = Path("/home/zomorod2/Saeit-staging")
START_MODULES = (
    "services.mpw_trx_commercial_web",
    "services.mpw_trx_public_catalog",
    "services.mpw_trx_guest_commerce",
    "services.mpw_trx_guest_delivery",
    "config.urls",
)
MAX_MODULES = 160
MAX_SOURCE_BYTES = 512 * 1024
ALLOWED_PREFIXES = (
    "services.mpw_", "services.mpw_tron_", "mpw_commerce.",
    "mpw_native_checkout.", "core.models", "config.urls",
)


def approved_module(module: str) -> bool:
    return (type(module) is str and module.isascii()
            and all(part.isidentifier() for part in module.split("."))
            and any(module == prefix.rstrip(".")
                    or module.startswith(prefix)
                    for prefix in ALLOWED_PREFIXES))


def static_imports(text: str) -> tuple[str, ...]:
    tree = ast.parse(text)
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names if approved_module(alias.name))
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            if node.module and approved_module(node.module):
                names.add(node.module)
    return tuple(sorted(names))


def readable_module(root: Path, module: str):
    if not approved_module(module):
        return None
    root = Path(root)
    if not root.is_dir() or root.is_symlink():
        return None
    parts = module.split(".")
    current = root
    for directory in parts[:-1]:
        current = current / directory
        if not current.is_dir() or current.is_symlink():
            return None
    path = current / (parts[-1] + ".py")
    try:
        if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= MAX_SOURCE_BYTES:
            return None
        return path.read_text(encoding="utf8")
    except (OSError, UnicodeError, ValueError):
        return None


def import_closure(root: Path):
    todo = list(START_MODULES)
    scanned = set()
    missing = set()
    parse_errors = set()
    bounded = True
    while todo:
        if len(scanned) >= MAX_MODULES:
            bounded = False
            break
        module = todo.pop(0)
        if module in scanned or not approved_module(module):
            continue
        scanned.add(module)
        raw = readable_module(root, module)
        if raw is None:
            missing.add(module)
            continue
        try:
            for child in static_imports(raw):
                if child not in scanned and child not in todo:
                    todo.append(child)
        except SyntaxError:
            parse_errors.add(module)
    return {
        "classification": "MPW_READONLY_CHECKOUT_IMPORT_CLOSURE",
        "read_only": True,
        "start_modules": len(START_MODULES),
        "inspected_modules": len(scanned),
        "missing_count": len(missing),
        "missing_import_modules": sorted(missing),
        "syntax_error_count": len(parse_errors),
        "source_tree_bounded": bounded,
        "module_paths_written": 0,
        "live_payment_enabled": False,
        "orders_created": 0,
        "customer_data_read": False,
        "checkout_deployable_verified": not missing and not parse_errors and bounded,
        "caveat": "Static AST closure cannot establish runtime imports, migrations, rights or settlement",
    }


if __name__ == "__main__":
    print(json.dumps(import_closure(APP_ROOT), sort_keys=True))
