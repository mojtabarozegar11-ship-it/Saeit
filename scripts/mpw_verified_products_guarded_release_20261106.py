#!/usr/bin/env python3
"""Surgical live conversion repair for MojPlayWin's verified revenue hub.

Fix malformed paragraph markup and connect the 12-tool audience to the three
real, currently purchasable store products. No order, payment or customer data
is accessed. The production file is backed up privately before atomic release.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import pwd
import re
import stat
import sys
import tempfile


ROOT = Path('/home/zomorod2/mojplaywin.com/mpw-editorial/revenue')
TARGET = ROOT / 'index.html'
BACKUPS = Path('/home/zomorod2/.local/share/mpw-verified-products-backups')
EXPECTED_SHA = '64012d10d7a565108709bcb14f98639e6790225b4c33491341d41496c261fd41'

FREE_OLD = (
    '<p>Free tools create draft outputs locally in your browser. Bespoke '
    'services require a written quotation; no payment is collected on these pages.'
    '<p class="mpw-free-tool-entry"><a '
    'href="/mpw-editorial/revenue/website-doctor/index.html#mpw-functional-tool">'
    'Open a free browser tool now →</a></p></p>'
)
FREE_NEW = FREE_OLD.replace('pages.<p class=', 'pages.</p><p class=').replace(
    'Open a free browser tool now →</a></p></p>',
    'Open a free browser tool now →</a></p>',
)
PRODUCTS_OLD = (
    '<section><h2>Buying a verified digital product</h2>'
    '<p>For currently published items, use the '
    '<a href="/store/">official MojPlayWin store</a> and inspect the '
    'individual product page. A product listing alone does not prove that '
    'checkout, entitlement or delivery is active.</p>'
    '<p><a href="/store/product/72/">Chess study book details</a> · '
    '<a href="/store/product/225/">Children\'s story book details</a></p></section>'
)
PRODUCTS_NEW = (
    '<section class="mpw-live-store-offers" aria-labelledby="mpw-live-products-title">'
    '<h2 id="mpw-live-products-title">Available digital products · buy with TRX</h2>'
    '<p>These three featured products have working guest checkout pages. '
    'You must provide a valid email address, but no account or wallet connection '
    'is required. Check the latest details before ordering.</p>'
    '<ul>'
    '<li><a href="/commerce/book/72/">Chess improvement guide · $7.50 · TRX checkout</a>'
    ' · <a href="/store/product/72/">Book details</a></li>'
    '<li><a href="/commerce/book/225/">Taniya illustrated story · $4.00 · TRX checkout</a>'
    ' · <a href="/store/product/225/">Story details</a></li>'
    '<li><a href="/commerce/book/879/">Atelier Interior website kit · $6.80 · TRX checkout</a>'
    ' · <a href="/store/product/879/">Kit details</a></li>'
    '</ul>'
    '<p>Payment is native TRX on the TRON network only. Use the exact amount '
    'and address from your own invoice. Download access is tied to your '
    'original browser session after verified payment. Emailed receipts and '
    'cross-device recovery are not currently available. '
    '<a href="/commerce/trx-easy/">See the complete eligible catalog</a> '
    'or <a href="/store/">compare the featured products</a>.</p>'
    '</section>'
)


def digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def transform(content: bytes) -> bytes:
    page = content.decode('utf-8', 'strict')
    if len(content) > 250000 or len(content) < 12000:
        raise RuntimeError('Unexpected source length')
    if page.count(FREE_OLD) != 1 or page.count(PRODUCTS_OLD) != 1:
        raise RuntimeError('Production markup differs from audited source')
    if page.count('class="mpw-direct-free-tool"') != 12:
        raise RuntimeError('Twelve working utility links must remain intact')
    if 'mpw-live-store-offers' in page:
        raise RuntimeError('This release has already been applied')
    new = page.replace(FREE_OLD, FREE_NEW).replace(PRODUCTS_OLD, PRODUCTS_NEW)
    if new.count('class="mpw-live-store-offers"') != 1:
        raise RuntimeError('Missing new live product block')
    for pid in ('72', '225', '879'):
        if new.count(f'href="/commerce/book/{pid}/"') != 1:
            raise RuntimeError('Unexpected live checkout product link count')
    if new.count('class="mpw-direct-free-tool"') != 12:
        raise RuntimeError('Tool linking changed')
    if new.replace(FREE_NEW, FREE_OLD).replace(PRODUCTS_NEW, PRODUCTS_OLD) != page:
        raise RuntimeError('Unexpected edits beyond the two audited replacements')
    return new.encode('utf-8')


def guard() -> None:
    if pwd.getpwuid(os.geteuid()).pw_name != 'zomorod2':
        raise RuntimeError('Wrong hosting account')
    if ROOT.is_symlink() or not ROOT.is_dir() or ROOT.resolve() != ROOT:
        raise RuntimeError('Unexpected hosting directory')
    if TARGET.is_symlink() or not TARGET.is_file():
        raise RuntimeError('Invalid revenue index path')
    info = TARGET.stat()
    if info.st_uid != os.geteuid() or info.st_nlink != 1 or stat.S_IMODE(info.st_mode) & 0o022:
        raise RuntimeError('Unexpected ownership or file mode')
    if BACKUPS.is_symlink() or BACKUPS.parent.is_symlink():
        raise RuntimeError('Unsafe backup directory')


def atomic_write(content: bytes, mode: int) -> None:
    fd, name = tempfile.mkstemp(prefix='.mpw-verified-products-', dir=str(ROOT))
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, TARGET)
        dirfd = os.open(ROOT, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(dirfd)
        finally:
            os.close(dirfd)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def backup_paths(release_id: str) -> tuple[Path, Path]:
    if not re.fullmatch(r'[0-9]{8,20}', release_id):
        raise RuntimeError('Invalid release id')
    return (BACKUPS / (release_id + '.original.html'),
            BACKUPS / (release_id + '.published.sha256'))


def main(op: str, release_id: str = '') -> None:
    if op == 'selftest':
        # Source cannot be read from this local environment; check static
        # replacement inverses and require the real live hash on cPanel.
        assert FREE_NEW != FREE_OLD and PRODUCTS_NEW != PRODUCTS_OLD
        assert '<p class="mpw-free-tool-entry">' in FREE_NEW
        assert FREE_NEW.count('</p>') == 2
        for pid in ('72', '225', '879'):
            assert PRODUCTS_NEW.count(f'href="/commerce/book/{pid}/"') == 1
        print('MPW_VERIFIED_PRODUCT_RELEASE_SELFTEST=PASS')
        return

    guard()
    old = TARGET.read_bytes()
    if op in ('preflight', 'publish'):
        if digest(old) != EXPECTED_SHA:
            raise RuntimeError('Current live source has changed; refusing publication')
        new = transform(old)
        if op == 'preflight':
            print('MPW_VERIFIED_PRODUCTS_PREFLIGHT=PASS new_sha256=' + digest(new))
            return

        backup, marker = backup_paths(release_id)
        BACKUPS.mkdir(parents=True, mode=0o700, exist_ok=True)
        if stat.S_IMODE(BACKUPS.stat().st_mode) != 0o700:
            raise RuntimeError('Backup folder is not private')
        if backup.exists() or marker.exists() or backup.is_symlink() or marker.is_symlink():
            raise RuntimeError('Release id already used')
        fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(old)
            stream.flush()
            os.fsync(stream.fileno())
        fd = os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write((digest(new) + '\n').encode())
            stream.flush()
            os.fsync(stream.fileno())
        if digest(TARGET.read_bytes()) != digest(old):
            raise RuntimeError('Concurrent live source change')
        try:
            atomic_write(new, stat.S_IMODE(TARGET.stat().st_mode))
            if TARGET.read_bytes() != new:
                raise RuntimeError('Published file failed verification')
        except BaseException:
            if digest(TARGET.read_bytes()) == digest(new):
                atomic_write(old, stat.S_IMODE(TARGET.stat().st_mode))
            raise
        print('MPW_VERIFIED_PRODUCTS_PUBLISHED=PASS sha256=' + digest(new))
        return

    if op == 'rollback':
        backup, marker = backup_paths(release_id)
        if not backup.is_file() or not marker.is_file() or backup.is_symlink() or marker.is_symlink():
            raise RuntimeError('Release backup missing')
        if digest(old) != marker.read_text().strip():
            raise RuntimeError('Live file changed; refusing rollback')
        previous = backup.read_bytes()
        if digest(previous) != EXPECTED_SHA:
            raise RuntimeError('Backup differs from expected original')
        atomic_write(previous, stat.S_IMODE(TARGET.stat().st_mode))
        print('MPW_VERIFIED_PRODUCTS_ROLLBACK=PASS')
        return
    raise RuntimeError('Expected selftest, preflight, publish or rollback')


if __name__ == '__main__':
    main(*sys.argv[1:])
