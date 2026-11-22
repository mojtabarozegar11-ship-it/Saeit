#!/usr/bin/env python3
"""Read-only, bounded attestation of the effective native Zomorod store PHP.

This file is piped to python3 over the pre-existing pinned SSH relay. It is
never installed on cPanel and must not modify files, permissions or databases.
No private PHP contents or customer data are printed, only SHA-256 and CSS flags.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat

HOME = Path("/home/zomorod2")
MAX_BYTES = 4_000_000
CSS_RULE = ".grid article small.muted{display:block;max-width:100%;overflow-wrap:anywhere;word-break:break-word}"
GRID_RULE = "grid-template-columns:repeat(auto-fit,minmax(min(100%,255px),1fr))"
PATHS = {
    "public_index": "public_html/store/index.php",
    "private_store_module": ".private/zomorod-business/site_store.php",
}
PARENTS = ("public_html", "public_html/store", ".private", ".private/zomorod-business")


def bounded_regular_file(root: Path, relative: str) -> bytes:
    path = root / relative
    for parent in PARENTS:
        if path == root / parent or root / parent in path.parents:
            if (root / parent).is_symlink():
                raise RuntimeError("symlink_parent_refused")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
    try:
        meta = os.fstat(fd)
        if not stat.S_ISREG(meta.st_mode):
            raise RuntimeError("not_regular_file")
        if meta.st_size > MAX_BYTES:
            raise RuntimeError("file_size_limit")
        with os.fdopen(os.dup(fd), "rb") as handle:
            data = handle.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise RuntimeError("file_read_limit")
        return data
    finally:
        os.close(fd)


def inspect(root: Path = HOME, enforce_home: bool = True) -> dict:
    if enforce_home and root.resolve() != HOME:
        raise RuntimeError("unexpected_account_home")
    result = {
        "scope": "native_store_cpanel_readonly",
        "verified_home": str(root.resolve() == HOME),
        "site_writes": 0,
        "forms_submitted": 0,
        "payments": 0,
        "authentication_attempts": 0,
        "private_content_disclosed": False,
    }
    for key, rel in PATHS.items():
        data = bounded_regular_file(root, rel)
        result[key + "_sha256"] = hashlib.sha256(data).hexdigest()
        result[key + "_bytes"] = len(data)
        if key == "public_index":
            text = data.decode("utf8", errors="replace")
            result["active_file_wrap_rule_present"] = CSS_RULE in text
            result["active_file_grid_rule_present"] = GRID_RULE in text
            result["active_file_has_native_db_call"] = "zmStoreDb($private)" in text
    result["active_css_pair_present"] = (
        result["active_file_wrap_rule_present"] and result["active_file_grid_rule_present"]
    )
    result["verified_public_http_serving_parity"] = False
    return result


if __name__ == "__main__":
    print(json.dumps(inspect(), ensure_ascii=False, sort_keys=True))
