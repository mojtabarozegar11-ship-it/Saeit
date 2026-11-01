#!/usr/bin/env python3
"""S-01: prove a narrow, rollback-friendly TRX-only rate patch applies in memory.

Runs read-only on the exact cPanel source. No source bytes or secrets leave host;
no DB, network quote, order, payment, file write or publication is performed.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
from pathlib import Path
import stat

APP = Path("/home/zomorod2/Saeit-staging")
EXPECTED = {
    "buyer": (
        APP / "mpw_commerce/buyer_wallets.py",
        "851dd2729037abb0d1e42721372df34b7d3d5ab6c839627d9ccee0ee8eadb596",
    ),
    "rate": (
        APP / "scripts/mojplaywin_direct_wallet_rates.py",
        "daf453478b35412a2e3a4e15c466177cf4045a2162b6f435a51146a665e38a48",
    ),
}


def _transform(name, raw):
    patches = {
        "buyer": (
            ("snap=fetch_fresh_rates()",
             "snap=fetch_fresh_rates(required_assets=(asset,))"),
        ),
        "rate": (
            ("def parse_coin_gecko_rates(document, now_epoch):",
             "def parse_coin_gecko_rates(document, now_epoch, *, required_assets=(\"ETH\", \"TRX\")):"),
            ("    result = {}\n    for symbol, coin_id in ((\"ETH\", \"ethereum\"), (\"TRX\", \"tron\")):",
             "    if type(required_assets) is not tuple or required_assets not in (\n"
             "        (\"ETH\",), (\"TRX\",), (\"ETH\", \"TRX\")\n"
             "    ):\n"
             "        raise RateFeedUnavailable(\"Invalid requested rate assets\")\n"
             "    result = {}\n"
             "    for symbol, coin_id in ((\"ETH\", \"ethereum\"), (\"TRX\", \"tron\")):\n"
             "        if symbol not in required_assets:\n"
             "            continue"),
            ("def fetch_fresh_rates(*, fetch=urlopen, now=None):",
             "def fetch_fresh_rates(*, fetch=urlopen, now=None, required_assets=(\"ETH\", \"TRX\")):"),
            ("return parse_coin_gecko_rates(doc, now)",
             "return parse_coin_gecko_rates(doc, now, required_assets=required_assets)"),
        ),
    }
    text = raw.decode("utf8")
    for old, new in patches[name]:
        if text.count(old) != 1:
            raise ValueError("Unexpected source anchor for " + name)
        text = text.replace(old, new, 1)
    result = text.encode("utf8")
    compile(result, "<candidate-" + name + ">", "exec")
    return result


def _read(name):
    path, sha = EXPECTED[name]
    if (APP.is_symlink() or APP.resolve() != APP or path.is_symlink()
            or path.parent.is_symlink() or APP not in path.parents):
        raise ValueError("Unsafe source path")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                or not 0 < info.st_size <= 200_000
                or stat.S_IMODE(info.st_mode) & 0o022):
            raise ValueError("Unsafe source attributes")
        with os.fdopen(os.dup(fd), "rb") as stream:
            raw = stream.read(200_001)
        if len(raw) != info.st_size or hashlib.sha256(raw).hexdigest() != sha:
            raise ValueError("Source changed since audit")
        return raw
    finally:
        os.close(fd)


def _function(tree, name):
    return next((n for n in tree.body if isinstance(n, ast.FunctionDef)
                 and n.name == name), None)


def classify_current(current):
    result = {}
    for name in EXPECTED:
        new = _transform(name, current[name])
        tree = ast.parse(new)
        result[name + "_patchable"] = len(new) > len(current[name])
        if name == "buyer":
            fn = _function(tree, "fetch_server_rate")
            result["buyer_pins_requested_asset"] = any(
                isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                and n.func.id == "fetch_fresh_rates"
                and any(k.arg == "required_assets" for k in n.keywords)
                for n in ast.walk(fn))
        else:
            fn = _function(tree, "parse_coin_gecko_rates")
            fetch = _function(tree, "fetch_fresh_rates")
            result["rate_functions_keep_existing_names"] = fn is not None and fetch is not None
            result["rate_quote_accepts_requested_assets"] = (
                any(a.arg == "required_assets" for a in fn.args.kwonlyargs)
                and any(a.arg == "required_assets" for a in fetch.args.kwonlyargs))
    result["db_accessed"] = False
    result["payments_created"] = False
    result["source_changed"] = False
    result["release_permitted"] = False
    return result


def main():
    if os.geteuid() == 0:
        raise RuntimeError("Refuse privileged account")
    doc = classify_current({name: _read(name) for name in EXPECTED})
    print("MPW_TRX_PATCH_PLAN=" + json.dumps(doc, sort_keys=True))


if __name__ == "__main__":
    main()
