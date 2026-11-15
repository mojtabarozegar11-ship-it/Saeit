"""Static source-closure gate for the guarded MojPlayWin TRON producer.

It checks only repository files and symlink safety. It does not import Django,
connect to a database, call RPC, send email, or enable checkout.
"""
from __future__ import annotations

from pathlib import Path


REQUIRED = (
    "mpw_commerce/__init__.py",
    "mpw_commerce/apps.py",
    "mpw_commerce/models.py",
    "mpw_commerce/migrations/0001_initial.py",
    "mpw_commerce/migrations/0002_guest_trx_delivery.py",
    "mpw_commerce/buyer_wallets.py",
    "mpw_commerce/downloads.py",
    "mpw_commerce/entitlements.py",
    "mpw_commerce/invoicing.py",
    "mpw_commerce/policy.py",
    "mpw_commerce/settlement.py",
    "services/mpw_trx_commercial_chain.py",
    "services/mpw_trx_commercial_context.py",
    "services/mpw_tron_readonly_deposit_candidates.py",
    "services/mpw_trx_commercial_web.py",
    "services/mpw_walletless_commercial_intent.py",
    "services/mpw_trx_walletless_core.py",
    "scripts/mojplaywin_native_chain_verify.py",
    "scripts/mojplaywin_direct_wallet_rates.py",
    "scripts/mpw_tron_public_dual_probe_readonly_20261023.py",
)


def missing_paths(root: Path) -> list[str]:
    """Reject symlinked files *and ancestors*, even when targets stay in-tree."""
    root = Path(root)
    if root.is_symlink():
        return list(REQUIRED)
    try:
        root = root.resolve(strict=True)
    except (OSError, RuntimeError):
        return list(REQUIRED)
    missing = []
    for relative in REQUIRED:
        parts = Path(relative).parts
        candidate = root.joinpath(*parts)
        # Resolving first hides an in-repository symlink and makes is_symlink()
        # on the resolved path always report False. Inspect original segments.
        segments = (root.joinpath(*parts[:index])
                    for index in range(1, len(parts) + 1))
        if any(segment.is_symlink() for segment in segments):
            missing.append(relative)
            continue
        try:
            resolved = candidate.resolve(strict=True)
            resolved.relative_to(root)
        except (OSError, ValueError, RuntimeError):
            missing.append(relative)
            continue
        if not candidate.is_file():
            missing.append(relative)
    return missing


def assert_source_closure(root: Path) -> None:
    missing = missing_paths(root)
    if missing:
        raise RuntimeError("Missing guarded commerce dependencies: " + ", ".join(missing))


if __name__ == "__main__":
    import json
    import sys

    root = Path(sys.argv[1]) if len(sys.argv) == 2 else Path.cwd()
    result = {"missing": missing_paths(root), "source_closure": not missing_paths(root)}
    print(json.dumps(result, sort_keys=True))
    raise SystemExit(0 if result["source_closure"] else 2)
