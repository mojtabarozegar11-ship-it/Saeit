"""Opt-in CLI for one bounded automatic TRON inbound scan. NOT scheduled or deployed.

Example (private production operator ONLY, after source and address ownership audits):
  MPW_TRON_DB=/safe/private/checkout.sqlite3 MPW_TRON_LOCK=/safe/private/scan.lock \
    MPW_TRON_API_KEY=... python -m mpw_tron_pro.worker --once

No seed phrases, withdrawal keys, signing or public control endpoints.
"""
from __future__ import annotations

import argparse
import fcntl
import os
from pathlib import Path

from .core import CheckoutError
from .ledger import InvoiceLedger
from .reconcile import reconcile_pending


def scan_once(db_filename: str, lock_filename: str, *, api_key: str = '',
              reconcile=reconcile_pending) -> dict:
    db_path, lock_path = Path(db_filename), Path(lock_filename)
    if not db_path.is_file() or db_path.is_symlink() or lock_path.is_symlink():
        raise CheckoutError('Operator database must exist and must not be a symlink')
    if db_path.resolve() == lock_path.resolve():
        raise CheckoutError('Lock path cannot overwrite database')
    # Must be in the same private folder, never an arbitrary world-readable path.
    if db_path.parent.resolve() != lock_path.parent.resolve():
        raise CheckoutError('Operator database and lock must share a private directory')
    if db_path.parent.stat().st_mode & 0o077:
        raise CheckoutError('Operator database directory permissions are not private')
    fd = os.open(lock_path, os.O_RDWR | os.O_CREAT | getattr(os,'O_NOFOLLOW',0), 0o600)
    try:
        if os.fstat(fd).st_mode & 0o077:
            raise CheckoutError('Worker lock permissions are insecure')
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise CheckoutError('Another reconciliation worker is already active') from exc
        ledger = InvoiceLedger(db_path)
        result = reconcile(ledger, max_invoices=20, api_key=api_key)
        ledger.record_scan_run(result)
        return result
    finally:
        os.close(fd)


def main():
    parser = argparse.ArgumentParser(description='Isolated bounded TRON scanner (no signing or payouts)')
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    if not args.once:
        parser.error('No scanning without the explicit --once operator flag')
    db = os.environ.get('MPW_TRON_DB','')
    lock = os.environ.get('MPW_TRON_LOCK','')
    if not db or not lock:
        parser.error('Private MPW_TRON_DB and MPW_TRON_LOCK are required')
    report = scan_once(db, lock, api_key=os.environ.get('MPW_TRON_API_KEY',''))
    # Counters only: never emit wallet addresses, buyers, tokens or tx hashes.
    print('TRON_SCAN_COUNTS', ' '.join(f'{k}={v}' for k,v in sorted(report.items())))


if __name__ == '__main__':
    main()