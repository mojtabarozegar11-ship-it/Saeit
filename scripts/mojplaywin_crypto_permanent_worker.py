#!/usr/bin/env python3
"""Opt-in, one-pass ETH/TRX commerce supervisor for MojPlayWin ONLY.

A trusted cron or systemd timer may invoke this script repeatedly *after*
verified isolated deployment. It does not install a timer, switch on any sale
flag, touch wallets/private keys, or create a payment. The old sitewide
mpw_commerce app must actually be installed and tested on that isolated host.
"""
from __future__ import annotations

import argparse
import fcntl
import os
from pathlib import Path
import stat
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
RELEASE_FLAGS = (
    "MPW_COMMERCE_RELEASE_READY",
    "MPW_COMMERCE_CUSTOMER_HTTP_ENABLED",
    "MPW_COMMERCE_INVOICING_ENABLED",
    "MPW_COMMERCE_BUYER_SIGNATURE_ENABLED",
    "MPW_COMMERCE_SETTLEMENT_ENABLED",
    "MPW_COMMERCE_REAL_RPC_ENABLED",
    "MPW_COMMERCE_AUTORECONCILE_ENABLED",
    "MPW_COMMERCE_DOWNLOADS_ENABLED",
)
OPERATIONS_FLAGS = (
    "MPW_COMMERCE_ISOLATED_RUNTIME_CERTIFIED",
    "MPW_COMMERCE_CONTINUOUS_OPERATIONS_ENABLED",
)


def ready(settings_obj, installed_apps: set[str]) -> tuple[bool, tuple[str, ...]]:
    """Read-only, deny-by-default test; never include secrets in diagnostics."""
    missing = tuple(
        name for name in (*OPERATIONS_FLAGS, *RELEASE_FLAGS)
        if getattr(settings_obj, name, False) is not True
    )
    if "mpw_commerce" not in installed_apps:
        missing += ("mpw_commerce:not_installed",)
    if "mpw_native_checkout" not in installed_apps:
        missing += ("mpw_native_checkout:not_installed",)
    return not missing, missing


def lock_path_is_private(root: Path, path: Path) -> bool:
    """Keep the scheduler lock out of document roots and shared site folders."""
    if not path.is_absolute() or not path.parent.is_dir():
        return False
    try:
        root = root.resolve(strict=True)
        parent = path.parent.resolve(strict=True)
        path.relative_to(parent)  # a lock file is a direct child only
        if parent == root or root in parent.parents:
            return False
        mode = parent.stat().st_mode
        return stat.S_ISDIR(mode) and mode & 0o077 == 0 and not path.is_symlink()
    except (OSError, ValueError):
        return False


def one_pass(root: Path, lock_path: Path, *, runner=subprocess.run, python=sys.executable):
    if not lock_path_is_private(root, lock_path):
        return "unsafe_private_lock"
    # The lock is only created after every release/isolation gate has passed.
    flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(str(lock_path), flags, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return "another_cycle_running"
        for name in ("mpw_commerce_reconcile", "mpw_commerce_fulfill_courses"):
            result = runner(
                [python, str(root / "manage.py"), name],
                cwd=str(root),
                timeout=120,
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                # No stdout/stderr: provider errors and secrets never leak.
                return "cycle_failed"
        return "cycle_passed"
    except (OSError, subprocess.TimeoutExpired):
        return "cycle_failed"
    finally:
        os.close(fd)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Isolated MojPlayWin crypto one-pass worker")
    parser.add_argument("--check", action="store_true", help="read-only eligibility probe")
    parser.add_argument("--once", action="store_true", help="one bounded reconciliation cycle")
    opts = parser.parse_args(argv)
    if opts.check == opts.once:
        parser.error("choose exactly one of --check or --once")
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django
    from django.apps import apps
    from django.conf import settings
    django.setup()
    ok, missing = ready(settings, set(apps.app_configs))
    if not ok:
        print("MPW_CRYPTO_WORKER=DISABLED missing_controls=" + str(len(missing)))
        return 1 if opts.once else 0
    if opts.check:
        print("MPW_CRYPTO_WORKER=ELIGIBLE not_a_live_payment_test")
        return 0
    lock = Path(os.environ.get("MPW_COMMERCE_PRIVATE_LOCK_PATH", ""))
    outcome = one_pass(ROOT, lock)
    print("MPW_CRYPTO_WORKER=" + outcome)
    return 0 if outcome in ("cycle_passed", "another_cycle_running") else 1


if __name__ == "__main__":
    raise SystemExit(main())
