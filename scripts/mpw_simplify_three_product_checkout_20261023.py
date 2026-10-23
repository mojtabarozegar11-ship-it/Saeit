#!/usr/bin/env python3
"""Bounded live copy and CTA correction for MojPlayWin's three sale products."""
from __future__ import annotations
import hashlib, json, os, re, stat, sys, tempfile
from pathlib import Path
from types import SimpleNamespace

ROOT=Path('/home/zomorod2/Saeit-staging')
HOME=Path('/home/zomorod2')
STORE=ROOT/'core/templates/mojplaywin/store.html'
EXPECTED={72:('The Science and Practice of Chess Improvement','7.50'),
          225:('Taniya and the Little Baker Worms','4.00'),
          879:('Atelier Interior — Client-Ready Website Kit','6.80')}
START='<!-- MPW_TWO_BOOKS_PUBLIC_CATALOG_V1_START -->'
END='<!-- MPW_TWO_BOOKS_PUBLIC_CATALOG_V1_END -->'
OLD_BUY={
 72:'<p><a class="mpw-crypto-buy" href="/commerce/book/72/" style="display:inline-block;padding:10px 20px;border:1px solid #9ed0ba;border-radius:12px;background:#176052;color:#fff;font-weight:700;text-decoration:none">Buy now — ETH / TRX</a></p>',
 225:'<p><a class="mpw-crypto-buy" href="/commerce/book/225/" style="display:inline-block;padding:10px 20px;border:1px solid #9ed0ba;border-radius:12px;background:#176052;color:#fff;font-weight:700;text-decoration:none">Buy now — ETH / TRX</a></p>',
}
OLD_INTRO='Secure purchases use verified ETH or TRX settlement; private PDF access becomes available only after confirmed payment.'
NEW_INTRO='Each book has a secure TRX invoice checkout. Private PDFs unlock only after independent on-chain payment confirmation.'
OLD_STATUS='Available now · verified crypto payment'
NEW_STATUS='TRX checkout available · account required'
OLD_CHECKOUT='Go to secure checkout ↗'
NEW_CHECKOUT='Buy securely with TRX ↗'
OLD_KIT='Buy website kit — secure ETH/TRX checkout ↗'

def fail(message): raise RuntimeError(message)
def digest(raw): return hashlib.sha256(raw).hexdigest()
def backup_path(run):
    if not re.fullmatch(r'[0-9]{8,20}',run): fail('Invalid release run id')
    return HOME/f'.mpw-three-product-cta-{run}.bak'

def transform(source):
    if source.count(START)!=1 or source.count(END)!=1:
        fail('Expected exactly one bounded two-book catalog block')
    if source.count('id="atelier-original-vector-879"')!=1:
        import json
        i=source.lower().find('atelier')
        print('MPW_STOREFRONT_SOURCE_DIAGNOSTIC='+json.dumps({
            'sha256':digest(source.encode('utf-8')),'bytes':len(source),
            'catalog_markers':[source.count(START),source.count(END)],
            'atelier_identifier_variants':{k:source.count(k) for k in (
                'atelier-original-vector-879','id="atelier-original-vector-879"',
                "id='atelier-original-vector-879'",'Atelier Interior')},
            'excerpt':source[max(0,i-180):i+500] if i>=0 else ''},ensure_ascii=False,sort_keys=True))
        fail('Expected exactly one Atelier product block')
    for pk,old in OLD_BUY.items():
        if source.count(old)!=1: fail(f'Expected one legacy book CTA for {pk}')
        source=source.replace(old,'',1)
    for old,new,count in (
        (OLD_INTRO,NEW_INTRO,1),
        (OLD_STATUS,NEW_STATUS,2),
        (OLD_CHECKOUT,NEW_CHECKOUT,2),
        (OLD_KIT,'Buy securely with TRX ↗',1),
    ):
        if source.count(old)!=count: fail(f'Expected {count} copies of audited storefront text: {old}')
        source=source.replace(old,new)
    if 'ETH / TRX' in source or 'ETH/TRX' in source or 'mpw-crypto-buy' in source:
        fail('Unsupported or duplicate ETH/TRX purchase control remains')
    if source.count('Buy securely with TRX ↗')!=3:
        fail('Expected exactly one primary TRX purchase CTA per product')
    return source

def atomic(path,raw):
    mode=stat.S_IMODE(path.stat().st_mode)
    fd,tmp=tempfile.mkstemp(prefix='.mpw-three-product-cta-',dir=path.parent)
    try:
        os.fchmod(fd,mode)
        with os.fdopen(fd,'wb') as f:
            f.write(raw); f.flush(); os.fsync(f.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)

def verify_products():
    os.chdir(ROOT); sys.path.insert(0,str(ROOT))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
    import django; django.setup()
    from django.test import Client
    from core.models import Product
    from mpw_commerce.buyer_orders import _eligible
    from mpw_commerce.downloads import _private_file
    for pk,(title,price) in EXPECTED.items():
        p=Product.objects.get(pk=pk)
        if (p.title!=title or str(p.price)!=price or p.currency!='USD' or not p.active
            or not _eligible(p)):
            fail(f'Live commerce eligibility or price check failed for {pk}')
        path=_private_file(SimpleNamespace(product=p))
        if path.is_symlink() or not path.is_file(): fail(f'Private download is unavailable for {pk}')
    body=Client(HTTP_HOST='mojplaywin.com').get('/store/').content.decode('utf-8')
    for pk,(title,_) in EXPECTED.items():
        if title not in body or f'/store/product/{pk}/checkout/' not in body:
            fail(f'Public catalog listing or checkout link missing for {pk}')

def publish(run):
    if ROOT.is_symlink() or not ROOT.is_dir() or STORE.is_symlink() or not STORE.is_file():
        fail('Unexpected checkout root or store template')
    if not (ROOT/'manage.py').is_file(): fail('Django app root is incomplete')
    old=STORE.read_bytes()
    text=old.decode('utf-8')
    new=transform(text).encode('utf-8')
    if new==old: fail('Storefront already transformed; refusing duplicate release')
    verify_products()
    backup=backup_path(run)
    if backup.exists() or backup.is_symlink(): fail('Release backup already exists')
    with backup.open('xb') as f:
        os.fchmod(f.fileno(),0o600); f.write(old); f.flush(); os.fsync(f.fileno())
    try:
        if digest(STORE.read_bytes())!=digest(old): fail('Concurrent template update detected')
        atomic(STORE,new)
        from django.test import Client
        from django.urls import reverse
        body=Client(HTTP_HOST='mojplaywin.com').get('/store/').content.decode('utf-8')
        if body.count('Buy securely with TRX ↗')!=3 or 'ETH / TRX' in body or 'ETH/TRX' in body:
            fail('Rendered storefront CTA verification failed')
        if '/commerce/book/72/' in body or '/commerce/book/225/' in body:
            fail('Legacy book purchase route remains in the catalog')
        for pk in EXPECTED:
            if f'/store/product/{pk}/checkout/' not in body: fail(f'Checkout link missing for {pk}')
        print('MPW_THREE_PRODUCT_CATALOG_RELEASE='+json.dumps({
            'run':run,'products':list(EXPECTED),'one_trx_cta_each':True,
            'legacy_eth_ctas_removed':True,'private_files_ready':True,
            'before_sha256':digest(old),'after_sha256':digest(new)},sort_keys=True))
    except BaseException:
        if STORE.exists() and digest(STORE.read_bytes())==digest(new): atomic(STORE,old)
        raise

def rollback(run):
    backup=backup_path(run)
    if backup.is_symlink() or not backup.is_file(): fail('Release backup missing')
    old=backup.read_bytes()
    if STORE.is_symlink() or not STORE.is_file(): fail('Unsafe storefront template')
    current=STORE.read_bytes()
    if transform(old.decode('utf-8')).encode('utf-8')!=current:
        fail('Storefront changed after release; refusing to overwrite newer edits')
    atomic(STORE,old)
    print('MPW_THREE_PRODUCT_CATALOG_ROLLBACK='+json.dumps({'restored':True,'sha256':digest(old)},sort_keys=True))

def selftest():
    s=START+'\n'+OLD_INTRO+'\n'+OLD_STATUS*2+'\n'+OLD_CHECKOUT*2+'\n'
    s+='\n'.join(OLD_BUY.values())+'\n'
    s+='Buy website kit — secure ETH/TRX checkout ↗\n'
    s+='id="atelier-original-vector-879"\n/store/product/72/checkout/\n'
    s+='id="mpw-sale-book72" id="mpw-sale-book225"\n'+END
    out=transform(s)
    assert out.count('Buy securely with TRX ↗')==3
    assert 'ETH/TRX' not in out and 'ETH / TRX' not in out and 'mpw-crypto-buy' not in out
    try: transform(out)
    except RuntimeError: pass
    else: raise AssertionError('Duplicate transform accepted')
    print('MPW_THREE_PRODUCT_CATALOG_SELFTEST=PASS')

if __name__=='__main__':
    if len(sys.argv)==2 and sys.argv[1]=='selftest': selftest()
    elif len(sys.argv)==3 and sys.argv[1]=='publish': publish(sys.argv[2])
    elif len(sys.argv)==3 and sys.argv[1]=='rollback': rollback(sys.argv[2])
    else: raise SystemExit('Usage: selftest | publish|rollback RUN_ID')
