#!/usr/bin/env python3
"""Owner-gated, site-specific Passenger MOJ PROP emergency invoice hold.

SOURCE ONLY: no production authorization is inferred from a GitHub merge.
Run 'apply' only with a separate, explicit scoped production change approval.
It overrides the MOJ PROP invoice flag in the MojPlayWin Passenger entry,
NOT the shared .env symlink. No other brand, factory, database or wallet
is deliberately modified. An independent public URL check is mandatory.
A rollback could re-enable an unsafe legacy checkout; approve it separately.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import sys

PUBLIC_ROOT = Path('/home/zomorod2/mojplaywin.com')
WSGI = PUBLIC_ROOT / 'passenger_wsgi.py'
RESTART = PUBLIC_ROOT / 'tmp/restart.txt'
SOURCE_ROOT = Path('/home/zomorod2/Saeit-mojplaywin-integrated-20261119')
ENV = SOURCE_ROOT / '.env'
EXPECTED_SHARED_ENV = Path('/home/zomorod2/Saeit-staging/.env')
BACKUP_DIR = Path('/home/zomorod2/separated-backups/20261121/mojprop-wsgi-emergency-hold-20261121')
PINNED_ORIGINAL_SHA256 = 'ae8a40629b0b0d38da0e6a3c5112bda2b52419cf2dc592d4d9aad54c2be931bb'
ORIGINAL_APP = "APP='/home/zomorod2/Saeit-mojplaywin-integrated-20261119'"
BEFORE_IMPORT = "from config.wsgi import application"
OVERRIDE = (
    '# MOJPROP paid-invoice emergency hold; Passenger MojPlayWin only.\n'
    "os.environ['MPW_MOJPROP_TRX_RELEASE_ENABLED']='false'\n"
)
APPROVE_APPLY = 'OWNER_AUTHORIZED_MOJPROP_ONLY_PASSENGER_HOLD'
APPROVE_ROLLBACK = 'OWNER_AUTHORIZED_MOJPROP_UNSAFE_ROLLBACK_AFTER_REMEDIATION'


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _regular_owned(path: Path, *, symlink_allowed: bool = False) -> None:
    if path.is_symlink() and not symlink_allowed:
        raise RuntimeError('unexpected_symlink_refuse')
    if not path.is_file() or path.stat().st_uid != os.getuid():
        raise RuntimeError('owner_or_regular_file_precondition_failed')


def candidate(original: bytes) -> bytes:
    """Pure single-site edit, never edits the shared .env."""
    if _sha(original) != PINNED_ORIGINAL_SHA256:
        raise ValueError('passenger_wsgi_original_sha_drift_refuse')
    source = original.decode('utf-8')
    if source.count(ORIGINAL_APP) != 1 or source.count(BEFORE_IMPORT) != 1:
        raise ValueError('passenger_wsgi_expected_app_or_import_missing')
    if 'MPW_MOJPROP_TRX_RELEASE_ENABLED' in source:
        raise ValueError('passenger_wsgi_override_already_present')
    if source.count("os.environ.setdefault('DJANGO_SETTINGS_MODULE'") != 1:
        raise ValueError('django_settings_line_mismatch')
    if source.index("os.environ.setdefault('DJANGO_SETTINGS_MODULE'") > source.index(BEFORE_IMPORT):
        raise ValueError('django_settings_import_order_wrong')
    if not source.endswith('\n'):
        raise ValueError('unexpected_passenger_file_ending')
    return source.replace(BEFORE_IMPORT, OVERRIDE + BEFORE_IMPORT, 1).encode('utf-8')


def _atomic_replace(file: Path, data: bytes, mode: int) -> None:
    tmp = file.with_name('.mojprop_checkout_hold_' + str(os.getpid()) + '.new')
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, file)
    finally:
        if tmp.exists():
            tmp.unlink()


def _restart() -> None:
    _regular_owned(RESTART)
    os.utime(RESTART, None)


def _scope_check() -> dict:
    _regular_owned(WSGI)
    _regular_owned(RESTART)
    _regular_owned(ENV, symlink_allowed=True)
    if not ENV.is_symlink() or ENV.resolve() != EXPECTED_SHARED_ENV.resolve():
        raise RuntimeError('shared_env_symlink_target_has_drifted')
    if WSGI.parent.resolve() != PUBLIC_ROOT.resolve():
        raise RuntimeError('public_root_mismatch')
    current = WSGI.read_bytes()
    is_original = _sha(current) == PINNED_ORIGINAL_SHA256
    is_held = False
    if not is_original:
        checkpoint = BACKUP_DIR / 'original-passenger_wsgi.py'
        if checkpoint.is_file() and not checkpoint.is_symlink():
            old = checkpoint.read_bytes()
            is_held = (_sha(old) == PINNED_ORIGINAL_SHA256
                       and current == candidate(old))
    return {
        'source_pinned': is_original,
        'hold_installed': is_held,
        'unrecognized_source': not is_original and not is_held,
        'shared_env_unmodified': True,
        'production_scope_only': True,
    }


def _ledger_snapshot(original: bytes, after: bytes) -> None:
    if BACKUP_DIR.exists():
        raise RuntimeError('existing_recovery_checkpoint_refuse_overwrite')
    BACKUP_DIR.mkdir(parents=True, mode=0o700)
    os.chmod(BACKUP_DIR, 0o700)
    snap = BACKUP_DIR / 'original-passenger_wsgi.py'
    fd = os.open(snap, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, 'wb') as f:
        f.write(original)
        f.flush()
        os.fsync(f.fileno())
    data = {
        'scope': 'MojPlayWin Passenger entry only',
        'original_sha256': _sha(original),
        'hold_sha256': _sha(after),
        'shared_env_touched': False,
        'rollback_requires_new_approval': True,
        'production_external_http_verified': False,
        'zero_historical_invoices_verified_at_preflight': True,
    }
    receipt = BACKUP_DIR / 'manifest.json'
    fd = os.open(receipt, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, 'w') as f:
        json.dump(data, f, sort_keys=True, indent=2)
        f.flush()
        os.fsync(f.fileno())


def _read_only_actual_invoice_count() -> int:
    """Only SELECT COUNT(*) against the effective dedicated Moj Prop database."""
    sys.path.insert(0, str(SOURCE_ROOT))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    import django
    django.setup()
    from config.mojprop_db_router import MOJPROP_DB_ALIAS
    from prop_firm.models import PropSimulationPayment
    count = PropSimulationPayment.objects.using(MOJPROP_DB_ALIAS).count()
    if type(count) is not int or count < 0:
        raise RuntimeError('untrusted_invoice_count')
    return count


def apply(*, approval: str, confirmed_zero_open_invoices: bool) -> dict:
    if approval != APPROVE_APPLY or confirmed_zero_open_invoices is not True:
        raise PermissionError('requires_explicit_scope_approval_and_zero_invoices_attestation')
    state = _scope_check()
    if not state['source_pinned'] or state['unrecognized_source']:
        raise RuntimeError('live_wsgi_source_drift_refuse')
    if _read_only_actual_invoice_count() != 0:
        raise RuntimeError('historical_invoices_require_independent_reconciliation')
    original = WSGI.read_bytes()
    after = candidate(original)
    _ledger_snapshot(original, after)
    if WSGI.read_bytes() != original:
        raise RuntimeError('concurrent_wsgi_source_mutation_refuse')
    _atomic_replace(WSGI, after, stat.S_IMODE(WSGI.stat().st_mode))
    _restart()
    if WSGI.read_bytes() != after:
        raise RuntimeError('post_restart_file_not_exact_candidate')
    return {'hold_code_installed': True,
            'external_http_verification_required': True,
            'shared_env_unchanged': True}


def rollback(*, approval: str) -> dict:
    if approval != APPROVE_ROLLBACK:
        raise PermissionError('explicit_separate_rollback_authorization_required')
    state = _scope_check()
    if not state['hold_installed']:
        raise RuntimeError('expected_checkout_hold_not_exactly_present')
    original = (BACKUP_DIR / 'original-passenger_wsgi.py').read_bytes()
    if _sha(original) != PINNED_ORIGINAL_SHA256:
        raise RuntimeError('recovery_copy_checksum_mismatch')
    if WSGI.read_bytes() != candidate(original):
        raise RuntimeError('deployed_checkout_hold_drift')
    _atomic_replace(WSGI, original, stat.S_IMODE(WSGI.stat().st_mode))
    _restart()
    return {'rollback_code_installed': True,
            'warning': 'legacy checkout may reopen; verify separately'}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('audit', 'apply', 'rollback'))
    parser.add_argument('--approval', default='')
    parser.add_argument('--zero-open-invoices-confirmed', action='store_true')
    args = parser.parse_args()
    if args.operation == 'audit':
        result = _scope_check()
    elif args.operation == 'apply':
        result = apply(approval=args.approval,
                       confirmed_zero_open_invoices=args.zero_open_invoices_confirmed)
    else:
        result = rollback(approval=args.approval)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
