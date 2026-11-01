#!/usr/bin/env python3
"""Guarded guest-checkout conversion copy and direct purchase links for MojPlayWin books."""
import hashlib, json, os, re, stat, sys, tempfile
from pathlib import Path

HOME = Path('/home/zomorod2')
APP = HOME / 'Saeit-staging'
STORE = APP / 'core/templates/mojplaywin/store.html'
WSGI = HOME / 'mojplaywin.com/passenger_wsgi.py'
COPY_OLD = "Open a product page to confirm its current price and checkout options. Sign-in is required for the order-specific TRX invoice. Pay only the exact asset and amount shown on that invoice; network fees may apply. The private digital file is made available after payment is independently confirmed. Never send funds to an address found outside your verified order invoice."
COPY_NEW = "No account is required. Checkout accepts native TRX on the TRON network only; bank cards, USDT and other networks are not accepted. Your order invoice shows the exact TRX amount and receiving address; network fees may apply. The private digital file unlocks after on-chain confirmation. Send funds only to the address shown in your live order invoice."
CTA_OLD = {
    72: "<a class=\"mpw-shop-secondary\" href=\"/store/product/72/\" aria-label=\"View The Science and Practice of Chess Improvement details and purchase\">View details &amp; purchase <span aria-hidden=\"true\">&nbsp;↗</span></a>",
    225: "<a class=\"mpw-shop-secondary\" href=\"/store/product/225/\" aria-label=\"View Taniya and the Little Baker Worms details and purchase\">View details &amp; purchase <span aria-hidden=\"true\">&nbsp;↗</span></a>",
}
CTA_NEW = {
    72: "<a class=\"mpw-shop-secondary\" href=\"/store/product/72/checkout/\" aria-label=\"Buy The Science and Practice of Chess Improvement with TRX\">Buy securely with TRX <span aria-hidden=\"true\">&nbsp;↗</span></a><a class=\"mpw-product-demo\" href=\"/store/product/72/\">Read full book details</a>",
    225: "<a class=\"mpw-shop-secondary\" href=\"/store/product/225/checkout/\" aria-label=\"Buy Taniya and the Little Baker Worms with TRX\">Buy securely with TRX <span aria-hidden=\"true\">&nbsp;↗</span></a><a class=\"mpw-product-demo\" href=\"/store/product/225/\">Read full story details</a>",
}
LEGACY_COPY_OLD = (
    'To purchase, sign in and follow the secure, order-specific checkout invoice. '
    'Private PDF access is granted only after confirmed payment. '
    'Never send funds outside your verified invoice.'
)

def preflight():
    if APP.is_symlink() or STORE.is_symlink() or WSGI.is_symlink():
        raise RuntimeError('Unsafe template scope')
    if not STORE.is_file() or not WSGI.is_file():
        raise RuntimeError('Store template or WSGI pin missing')
    if "APP='/home/zomorod2/Saeit-staging'" not in WSGI.read_text('utf8', 'replace'):
        raise RuntimeError('Shared Passenger root mismatch')

def patch(raw):
    text = raw.decode('utf8')
    changed = False
    if text.count(COPY_OLD) == 1:
        text = text.replace(COPY_OLD, COPY_NEW, 1)
        changed = True
    elif text.count(LEGACY_COPY_OLD):
        n = text.count(LEGACY_COPY_OLD)
        if n > 2:
            raise RuntimeError('Unexpected repeated legacy purchase notice')
        text = text.replace(LEGACY_COPY_OLD, COPY_NEW)
        changed = True
    elif text.count(COPY_NEW) < 1:
        raise RuntimeError('Expected guest-checkout notice missing')
    for pk in (72, 225):
        old, new = CTA_OLD[pk], CTA_NEW[pk]
        if text.count(old) == 1:
            text = text.replace(old, new, 1)
            changed = True
        elif text.count(new) != 1:
            raise RuntimeError('Book CTA drift: ' + str(pk))
    if text.count(COPY_NEW) < 1:
        raise RuntimeError('Guest checkout notice not installed')
    if text.count('href="/store/product/72/checkout/"') < 1 or text.count('href="/store/product/225/checkout/"') < 1:
        raise RuntimeError('Direct checkout links missing')
    return text.encode('utf8')

def backup(run):
    return HOME / ('.mpw-book-payment-explainer-' + run + '.bak')

def write(data):
    mode = stat.S_IMODE(STORE.stat().st_mode)
    fd, name = tempfile.mkstemp(dir=STORE.parent, prefix='.mpw-sale-note-')
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data); stream.flush(); os.fsync(stream.fileno())
        os.replace(name, STORE)
    finally:
        if os.path.exists(name):
            os.unlink(name)

def selftest():
    source = Path(__file__).resolve().parents[1] / 'core/templates/mojplaywin/store.html'
    before = source.read_bytes()
    after = patch(before)
    updated = after.decode('utf8')
    assert updated.count(COPY_NEW) == 1
    assert updated.count('href="/store/product/72/checkout/"') == 1
    assert updated.count('href="/store/product/225/checkout/"') == 1
    assert 'Sign-in is required for the order-specific TRX invoice.' not in updated
    assert patch(after) == after
    print('MPW_GUEST_PURCHASE_COPY_SELFTEST=PASS')

def publish(run):
    preflight()
    before = STORE.read_bytes()
    after = patch(before)
    p = backup(run)
    if p.exists() or p.is_symlink():
        raise RuntimeError('Backup collision')
    with p.open('xb') as stream:
        os.chmod(p, 0o600); stream.write(before); stream.flush(); os.fsync(stream.fileno())
    write(after)
    if STORE.read_bytes() != after:
        raise RuntimeError('Post-install mismatch')
    print('MPW_BUYER_PAYMENT_COPY=' + json.dumps({
        'installed': True, 'only_store_template': True, 'gateway_flags_untouched': True,
        'old_sha256': hashlib.sha256(before).hexdigest(),
        'new_sha256': hashlib.sha256(after).hexdigest(),
    }))

def rollback(run):
    preflight()
    p = backup(run)
    if p.is_symlink() or not p.is_file():
        raise RuntimeError('No private backup')
    old = p.read_bytes()
    if patch(old) != STORE.read_bytes():
        raise RuntimeError('Unrelated edits present; rollback blocked')
    write(old)
    print('MPW_BUYER_PAYMENT_COPY_ROLLBACK=PASS')

if __name__ == '__main__':
    if len(sys.argv) == 2 and sys.argv[1] == 'selftest':
        selftest()
    elif len(sys.argv) == 3 and sys.argv[1] in ('publish', 'rollback') and re.fullmatch(r'[0-9]{8,20}', sys.argv[2]):
        (publish if sys.argv[1] == 'publish' else rollback)(sys.argv[2])
    else:
        raise SystemExit('Expected selftest or publish|rollback RUN_ID')
