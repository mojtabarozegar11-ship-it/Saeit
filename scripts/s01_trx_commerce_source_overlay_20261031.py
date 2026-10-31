#!/usr/bin/env python3
"""Fail-closed S-01 TRX checkout source overlay PREVIEW, never a release tool.

This operates on the observed, separately deployed commerce module, which is
not part of this repository. It cannot install, restart, order or pay.
An independently restorable full site+effective Passenger DB backup and a
separate approved deployment gate are required before installation.
"""
from __future__ import annotations

import ast
import hashlib
import json
import sys
from pathlib import Path

EXPECTED_SOURCE_SHA256 = "a3015e62d0ae13d49935d1a1bf48a6971ee852599550dda2cd083aca9397d11b"
TARGET = Path("/home/zomorod2/Saeit-staging/services/mpw_trx_commercial_web.py")

# This preserves the live (USD per TRX, Unix timestamp) tuple contract.
# The already-reviewed TRX-only rate source must be deployed and SHA-verified
# separately; failure or stale data MUST NOT create a payable invoice.
NEW_FUNCTION = '''def _rate_provider():
    """TRX-only fresh USD quote; preserves the existing tuple contract."""
    from decimal import Decimal
    from scripts.mojplaywin_direct_wallet_rates import RateFeedUnavailable
    from scripts.s01_trx_rate_isolation_candidate import (
        TrustedRateUnavailable, fetch_trx_only,
    )
    try:
        observation = fetch_trx_only()
    except TrustedRateUnavailable as exc:
        raise RateFeedUnavailable("Trusted TRX rate unavailable") from exc
    if not Decimal("0.001") <= observation.usd_per_trx <= Decimal("100"):
        raise RateFeedUnavailable("TRX quote outside commerce safety range")
    return observation.usd_per_trx, observation.observed_at
'''


class SourceContractChanged(RuntimeError):
    """Refuse to alter a changed or unrecognized commerce source."""


def digest(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def _function(tree: ast.Module) -> ast.FunctionDef:
    found = [node for node in tree.body
             if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
             and node.name == "_rate_provider"]
    if len(found) != 1 or not isinstance(found[0], ast.FunctionDef):
        raise SourceContractChanged("Expected one synchronous rate provider")
    return found[0]


def _validate_contract(tree: ast.Module, fn: ast.FunctionDef) -> None:
    if fn.decorator_list or fn.args.args or fn.args.posonlyargs or fn.args.kwonlyargs \
            or fn.args.vararg or fn.args.kwarg:
        raise SourceContractChanged("Rate-provider signature changed")
    body = list(fn.body)
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
            and isinstance(body[0].value.value, str):
        body.pop(0)
    if len(body) == 3 and isinstance(body[0], ast.ImportFrom):
        original_import = body.pop(0)
        if original_import.module != "mpw_commerce.buyer_wallets" \
                or not any(alias.name == "fetch_server_rate" for alias in original_import.names):
            raise SourceContractChanged("Rate-provider original import changed")
    if len(body) != 2 or not isinstance(body[0], ast.Assign) or not isinstance(body[1], ast.Return):
        raise SourceContractChanged("Rate-provider body changed")
    assign = body[0]
    if len(assign.targets) != 1 or not isinstance(assign.targets[0], ast.Name):
        raise SourceContractChanged("Quote assignment changed")
    name = assign.targets[0].id
    call = assign.value
    if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Name) \
            or call.func.id != "fetch_server_rate" or len(call.args) != 1 or call.keywords \
            or not isinstance(call.args[0], ast.Constant) or call.args[0].value != "TRX":
        raise SourceContractChanged("Expected stale TRX rate call absent")
    ret = body[1].value
    if not isinstance(ret, ast.Tuple) or len(ret.elts) != 2:
        raise SourceContractChanged("Return tuple changed")
    for expr, attr in zip(ret.elts, ("usd_per_asset", "observed_at")):
        if not isinstance(expr, ast.Attribute) or expr.attr != attr \
                or not isinstance(expr.value, ast.Name) or expr.value.id != name:
            raise SourceContractChanged("Return field or order changed")
    # New provider imports the original RateFeedUnavailable class explicitly.
    # No fallback to an unrelated exception or unverified payable quote.


def build(original: bytes, *, expected_sha256: str = EXPECTED_SOURCE_SHA256) -> bytes:
    if digest(original) != expected_sha256:
        raise SourceContractChanged("Live source SHA drift; refuse overlay")
    try:
        source = original.decode("utf-8")
        tree = ast.parse(source)
    except (UnicodeDecodeError, SyntaxError) as exc:
        raise SourceContractChanged("Commerce source cannot be parsed") from exc
    fn = _function(tree)
    _validate_contract(tree, fn)
    if fn.col_offset != 0 or fn.end_lineno is None:
        raise SourceContractChanged("Provider location changed")
    lines = source.splitlines(keepends=True)
    replacement = NEW_FUNCTION
    if not replacement.endswith("\n"):
        raise SourceContractChanged("Missing final newline")
    revised = "".join(lines[:fn.lineno - 1]) + replacement + "".join(lines[fn.end_lineno:])
    compiled = ast.parse(revised)
    before_other = [ast.dump(n, include_attributes=False) for n in tree.body if n is not fn]
    after_fn = _function(compiled)
    after_other = [ast.dump(n, include_attributes=False) for n in compiled.body if n is not after_fn]
    if before_other != after_other:
        raise SourceContractChanged("Unexpected non-provider source modification")
    compile(revised, str(TARGET), "exec")
    return revised.encode("utf-8")


def actual_source_in_memory_smoke(candidate: bytes) -> None:
    """Execute ONLY the patched provider AST against stub modules, never Django."""
    from decimal import Decimal
    from types import ModuleType, SimpleNamespace
    from unittest.mock import patch

    fn = _function(ast.parse(candidate.decode("utf-8")))
    class OriginalRateError(Exception):
        pass
    class TrustedRateUnavailable(Exception):
        pass

    fake_scripts = ModuleType("scripts")
    fake_scripts.__path__ = []
    fake_market = ModuleType("scripts.mojplaywin_direct_wallet_rates")
    fake_market.RateFeedUnavailable = OriginalRateError
    fake_quote = ModuleType("scripts.s01_trx_rate_isolation_candidate")
    fake_quote.TrustedRateUnavailable = TrustedRateUnavailable
    fake_quote.fetch_trx_only = lambda: SimpleNamespace(
        usd_per_trx=Decimal("0.25"), observed_at=1793470000)
    scope = {}
    with patch.dict(sys.modules, {
        "scripts": fake_scripts,
        "scripts.mojplaywin_direct_wallet_rates": fake_market,
        "scripts.s01_trx_rate_isolation_candidate": fake_quote,
    }):
        exec(compile(ast.Module(body=[fn], type_ignores=[]),
                     "<exact-live-source-memory>", "exec"), scope)
        provider = scope["_rate_provider"]
        if provider() != (Decimal("0.25"), 1793470000):
            raise SourceContractChanged("Patched provider tuple smoke failed")
        fake_quote.fetch_trx_only = lambda: (_ for _ in ()).throw(
            TrustedRateUnavailable("stale"))
        try:
            provider()
        except OriginalRateError:
            pass
        else:
            raise SourceContractChanged("Stale quote did not fail closed")
        fake_quote.fetch_trx_only = lambda: SimpleNamespace(
            usd_per_trx=Decimal("150"), observed_at=1793470000)
        try:
            provider()
        except OriginalRateError:
            pass
        else:
            raise SourceContractChanged("Out-of-range quote did not fail closed")


def preview() -> None:
    if TARGET.is_symlink() or not TARGET.is_file():
        raise SourceContractChanged("Commerce source is not a regular file")
    original = TARGET.read_bytes()
    candidate = build(original)
    actual_source_in_memory_smoke(candidate)
    print("S01_TRX_PROVIDER_OVERLAY_PREVIEW=" + json.dumps({
        "status": "CODE_ONLY_NOT_INSTALLED",
        "source_sha256": digest(original),
        "candidate_sha256": digest(candidate),
        "source_bytes": len(original),
        "candidate_bytes": len(candidate),
        "target": "services/mpw_trx_commercial_web.py",
        "db_access": False,
        "production_writes": False,
        "actual_source_in_memory_smoke": "PASS",
        "orders_created": 0,
        "payments_created": 0,
        "requires_offhost_restore_and_approved_release": True,
    }, sort_keys=True))


if __name__ == "__main__":
    if sys.argv[1:] != ["preview"]:
        raise SystemExit("Only read-only preview is supported; install is disabled")
    preview()
