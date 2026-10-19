#!/usr/bin/env python3
"""Remove stale contradictory book-payment text from the two main storefront cards.
No payment code, databases, assets, subsites or shared app routes are touched.
"""
import hashlib,json,os,re,stat,sys,tempfile
from pathlib import Path
HOME=Path('/home/zomorod2')
APP=HOME/'Saeit-staging'
STORE=APP/'core/templates/mojplaywin/store.html'
WSGI=HOME/'mojplaywin.com/passenger_wsgi.py'
OPEN='<!-- MPW_TWO_BOOKS_PUBLIC_CATALOG_V1_START -->'
CLOSE='<!-- MPW_TWO_BOOKS_PUBLIC_CATALOG_V1_END -->'
ALERT='Checkout is not open. No payment should be sent without a verified order-specific invoice and confirmed digital delivery.'
ALERT_NEW='To purchase, sign in and follow the secure, order-specific checkout invoice. Private PDF access is granted only after confirmed payment. Never send funds outside your verified invoice.'
LATE='Downloads will be provided privately after confirmed payment once sales are enabled.'
LATE_NEW='Digital downloads are delivered privately after the payment has been verified on-chain and assigned to your order.'
GRAMMAR='Secure purchases opens through verified ETH or TRX settlement'
GRAMMAR_NEW='Secure purchases use verified ETH or TRX settlement'
def preflight():
    if APP.is_symlink() or STORE.is_symlink() or WSGI.is_symlink() or not STORE.is_file() or not WSGI.is_file():
        raise RuntimeError('Unsafe template scope')
    if "APP='/home/zomorod2/Saeit-staging'" not in WSGI.read_text('utf8','replace'):
        raise RuntimeError('Shared app root mismatch')
def patch(raw):
    text=raw.decode('utf8')
    if text.count(OPEN)!=1 or text.count(CLOSE)!=1:raise RuntimeError('Book catalog boundaries missing')
    a,rest=text.split(OPEN,1)
    segment,b=rest.split(CLOSE,1)
    if (segment.count(ALERT)!=2 or segment.count(LATE)!=1
        or segment.count('href="/store/product/72/checkout/"')!=1
        or segment.count('href="/store/product/225/checkout/"')!=1
        or segment.count('id="mpw-book-buyer-details"')!=1):
        raise RuntimeError('Unexpected store or checkout text drift')
    updated=segment.replace(ALERT,ALERT_NEW).replace(LATE,LATE_NEW).replace(GRAMMAR,GRAMMAR_NEW)
    if updated==segment:raise RuntimeError('No changes proposed')
    newer=(a+OPEN+updated+CLOSE+b).encode('utf8')
    if newer.replace(ALERT_NEW.encode(),ALERT.encode(),2).replace(LATE_NEW.encode(),LATE.encode(),1).replace(GRAMMAR_NEW.encode(),GRAMMAR.encode(),1)!=raw:
        raise RuntimeError('Non-reversible store change')
    return newer
def backup(r):return HOME/('.mpw-book-payment-explainer-'+r+'.bak')
def write(data):
    mode=stat.S_IMODE(STORE.stat().st_mode)
    fd,name=tempfile.mkstemp(dir=STORE.parent,prefix='.mpw-sale-note-')
    try:
        os.fchmod(fd,mode)
        with os.fdopen(fd,'wb') as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
        os.replace(name,STORE)
    finally:
        if os.path.exists(name):os.unlink(name)
def publish(r):
    preflight()
    before=STORE.read_bytes();after=patch(before);p=backup(r)
    if p.exists() or p.is_symlink():raise RuntimeError('Backup collision')
    with p.open('xb') as stream:os.chmod(p,0o600);stream.write(before);stream.flush();os.fsync(stream.fileno())
    write(after)
    if STORE.read_bytes()!=after:raise RuntimeError('Post-install mismatch')
    print('MPW_BUYER_PAYMENT_COPY='+json.dumps({'installed':True,'only_store_template':True,'gateway_flags_untouched':True,'old_sha256':hashlib.sha256(before).hexdigest(),'new_sha256':hashlib.sha256(after).hexdigest()}))
def rollback(r):
    preflight();p=backup(r)
    if p.is_symlink() or not p.is_file():raise RuntimeError('No backup')
    old=p.read_bytes()
    if patch(old)!=STORE.read_bytes():raise RuntimeError('Unrelated edits present; rollback blocked')
    write(old);print('MPW_BUYER_PAYMENT_COPY_ROLLBACK=PASS')
if __name__=='__main__':
    if len(sys.argv)!=3 or sys.argv[1] not in ('publish','rollback') or not re.fullmatch('[0-9]{8,20}',sys.argv[2]):
        raise SystemExit('Expected publish|rollback RUN_ID')
    (publish if sys.argv[1]=='publish' else rollback)(sys.argv[2])
