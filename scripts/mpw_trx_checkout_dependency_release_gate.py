#!/usr/bin/env python3
"""Read-only, fail-closed Passenger TRX checkout dependency release gate.

Run from the actual cPanel application's Python before switching WSGI targets.
This script does not create an order, read a wallet key, contact a price API,
modify any file, import Django, or bypass any checkout security requirement.

The three pinned sources are stored in the OWNER'S PRIVATE gateway vault,
not in the public Saeit checkout repository.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
from typing import Mapping

APP_ROOT = Path("/home/zomorod2/Saeit-mojprop-candidate-20261122")
PUBLIC_WSGI = Path("/home/zomorod2/mojplaywin.com/passenger_wsgi.py")

PINNED_SHA256 = {
    "mojplaywin_native_chain_verify.py":
        "c27eec10bf80014d7b88c284a8e7e94d0b590af5cc8ba5672972a2b43dadd8b4",
    "mojplaywin_direct_wallet_invoice.py":
        "409108730f7d4fbf3ad221e0264ed47335daa5f97ab74c721c38397e5ac133c4",
    "mojplaywin_direct_wallet_rates.py":
        "290eae3ed4669a8bb4b98fdcaafca469b37d19bc8a49acded133db46f467264c",
}

REQUIRED_SYMBOLS = {
    "mojplaywin_native_chain_verify.py": {"tron_address_to_hex", "verify_trx_transfer"},
    "mojplaywin_direct_wallet_invoice.py": {"SpotRate"},
    "mojplaywin_direct_wallet_rates.py": {"fetch_fresh_rates", "RateFeedUnavailable"},
}
MAX_SOURCE_BYTES = 256 * 1024


def _wsgi_targets_expected_app(source: str, expected: str) -> bool:
    """Parse top-level APP assignments without executing Passenger code.

    Exactly one literal string assignment is accepted. Duplicate, computed,
    nested, or otherwise ambiguous assignments fail closed because Passenger
    could use a different application root than the one being audited.
    """
    try:
        tree = ast.parse(source, filename="passenger_wsgi.py")
    except SyntaxError:
        return False

    values = []
    for node in tree.body:
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        else:
            continue
        if any(isinstance(target, ast.Name) and target.id == "APP"
               for target in targets):
            values.append(node.value)

    if len(values) != 1:
        return False
    value = values[0]
    return (
        isinstance(value, ast.Constant)
        and type(value.value) is str
        and value.value == expected
    )


def audit(
    app_root: Path,
    wsgi: Path,
    *,
    pinned_hashes: Mapping[str, str] = PINNED_SHA256,
    required_symbols: Mapping[str, set[str]] | None = REQUIRED_SYMBOLS,
) -> dict:
    """Return a non-secret result; do not mutate root or global Python state."""
    errors: list[str] = []
    files: dict[str, str] = {}
    app_root = Path(app_root)
    wsgi = Path(wsgi)
    if not app_root.is_dir() or app_root.is_symlink():
        errors.append("app_root_missing_or_symlink")
    scripts = app_root / "scripts"
    if not scripts.is_dir() or scripts.is_symlink():
        errors.append("app_scripts_missing_or_symlink")

    if not wsgi.is_file() or wsgi.is_symlink():
        errors.append("wsgi_missing_or_symlink")
    else:
        try:
            text = wsgi.read_text(encoding="utf-8")
            if not _wsgi_targets_expected_app(text, str(app_root)):
                errors.append("wsgi_effective_app_root_drift")
        except (OSError, UnicodeError):
            errors.append("wsgi_unreadable")

    for basename, expected_hash in pinned_hashes.items():
        if Path(basename).name != basename or not basename.endswith(".py"):
            errors.append("unsafe_module_name")
            continue
        path = scripts / basename
        if not path.is_file() or path.is_symlink():
            errors.append("missing_or_symlink:" + basename)
            continue
        try:
            if path.stat().st_size > MAX_SOURCE_BYTES:
                errors.append("oversized:" + basename)
                continue
            body = path.read_bytes()
            actual = hashlib.sha256(body).hexdigest()
            files[basename] = actual
            if actual != expected_hash:
                errors.append("sha256_mismatch:" + basename)
                continue
            tree = ast.parse(body.decode("utf-8"), filename=basename)
            compile(tree, str(path), "exec")
            if required_symbols is not None:
                declared = {
                    node.name
                    for node in tree.body
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                }
                if not set(required_symbols.get(basename, set())).issubset(declared):
                    errors.append("api_contract_missing:" + basename)
        except (OSError, SyntaxError, UnicodeError, ValueError):
            errors.append("source_unreadable_or_invalid:" + basename)

    return {
        "ready": not errors,
        "error_codes": sorted(set(errors)),
        "expected_modules": len(pinned_hashes),
        "checked_source_hashes": files,
        "checks": {
            "no_network_or_db_usage": True,
            "read_only": True,
            "does_not_prove_invoice_post_or_payment": True,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app-root", type=Path, default=APP_ROOT)
    parser.add_argument("--wsgi", type=Path, default=PUBLIC_WSGI)
    args = parser.parse_args()
    result = audit(args.app_root, args.wsgi)
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return 0 if result["ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
