#!/usr/bin/env python3
"""MojPlayWin TRX quote source-shape probe: read only, no source export or DB."""
from __future__ import annotations

import ast
import json
import os
from pathlib import Path
import stat

ROOT = Path("/home/zomorod2/Saeit-staging")
FILES = {
    "buyer": "mpw_commerce/buyer_wallets.py",
    "rates": "scripts/mojplaywin_direct_wallet_rates.py",
    "web": "services/mpw_trx_commercial_web.py",
}


def _read_source(path: Path) -> ast.Module:
    if (not path.is_absolute() or path.is_symlink()
            or path.parent.is_symlink() or ROOT not in path.parents):
        raise RuntimeError("Unsafe source path")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                or not 0 < info.st_size <= 200_000
                or stat.S_IMODE(info.st_mode) & 0o022):
            raise RuntimeError("Unsafe source file")
        with os.fdopen(os.dup(fd), "rb") as stream:
            data = stream.read(200_001)
        if len(data) != info.st_size:
            raise RuntimeError("Source read changed")
        return ast.parse(data, filename="<private-live-source>")
    finally:
        os.close(fd)


def _function(tree: ast.AST, name: str):
    return next((node for node in getattr(tree, "body", ())
                 if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                 and node.name == name), None)


def _has_kwarg_call(fn, callee: str, keyword: str):
    if fn is None:
        return False
    for node in ast.walk(fn):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id == callee and any(k.arg == keyword for k in node.keywords):
                return True
    return False


def _kwarg_declared(fn, name: str):
    return fn is not None and any(x.arg == name for x in fn.args.kwonlyargs)


def _literal_used(fn, literal: str):
    return bool(fn and any(isinstance(x, ast.Constant) and x.value == literal
                           for x in ast.walk(fn)))


def classify(trees: dict):
    buyer = _function(trees["buyer"], "fetch_server_rate")
    fetch = _function(trees["rates"], "fetch_fresh_rates")
    parser = _function(trees["rates"], "parse_coin_gecko_rates")
    provider = _function(trees["web"], "_rate_provider")
    return {
        "buyer_requests_asset_only": _has_kwarg_call(
            buyer, "fetch_fresh_rates", "required_assets"),
        "rate_fetch_accepts_assets": _kwarg_declared(fetch, "required_assets"),
        "rate_parser_accepts_assets": _kwarg_declared(parser, "required_assets"),
        "rate_parser_checks_observed_at": _literal_used(parser, "last_updated_at"),
        "web_requests_native_trx": _literal_used(provider, "TRX"),
        "passenger_effective_source_proven": False,
        "payment_created": False,
        "db_accessed": False,
        "release_permitted": False,
    }


def main():
    if (ROOT.is_symlink() or not ROOT.is_dir()
            or ROOT.resolve() != ROOT or os.geteuid() == 0):
        raise RuntimeError("Untrusted source root")
    trees = {name: _read_source(ROOT / relative)
             for name, relative in FILES.items()}
    print("MPW_TRX_SOURCE_SHAPE=" + json.dumps(classify(trees), sort_keys=True))


if __name__ == "__main__":
    main()
