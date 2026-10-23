#!/usr/bin/env python3
"""Bounded live copy and CTA correction for MojPlayWin's three sale products."""
from __future__ import annotations
import hashlib, json, os, re, stat, sys, tempfile
from pathlib import Path
from types import SimpleNamespace

ROOT=Path('/home/zomorod2/Saeit-staging')
HOME=Path('/home/zomorod2')
STORE=ROOT/'core/templates/mojplaywin/store.html'
PRODUCT_TEMPLATE=ROOT/'core/templates/brands/mojplaywin/product.html'
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
OLD_PRODUCT_PAYMENT='ETH/TRX'
OLD_ATELIER_CTA='Buy website kit — secure ETH/TRX checkout ↗'
NEW_ATELIER_CTA='Buy website kit securely with TRX ↗'

def fail(message): raise RuntimeError(message)
def digest(raw): return hashlib.sha256(raw).hexdigest()
def backup_path(run):
    if not re.fullmatch(r'[0-9]{8,20}',run): fail('Invalid release run id')
    return HOME/f'.mpw-three-product-cta-{run}.bak'

def transform(source):
    if source.count(START)!=1 or source.count(END)!=1:
        fail('Expected exactly one bounded two-book catalog block')
    if (source.count(NEW_INTRO)==1 and source.count(NEW_STATUS)==2
        and source.count(NEW_CHECKOUT)==2 and 'ETH / TRX' not in source
        and 'mpw-crypto-buy' not in source):
        return source
    for pk,old in OLD_BUY.items():
        if source.count(old)!=1: fail(f'Expected one legacy book CTA for {pk}')
        source=source.replace(old,'',1)
    for old,new,count in (
        (OLD_INTRO,NEW_INTRO,1),
        (OLD_STATUS,NEW_STATUS,2),
        (OLD_CHECKOUT,NEW_CHECKOUT,2),
    ):
        if source.count(old)!=count: fail(f'Expected {count} copies of audited storefront text: {old}')
        source=source.replace(old,new)
    if 'ETH / TRX' in source or 'mpw-crypto-buy' in source:
        fail('Unsupported or duplicate ETH/TRX purchase control remains')
    if source.count('Buy securely with TRX ↗')!=2:
        fail('Expected exactly one primary TRX purchase CTA per book')
    return source

def find_atelier_source():
    roots=(ROOT, HOME/'mojplaywin.com')
    suffixes={'.html','.htm','.php','.py','.js'}
    skip={'.git','node_modules','venv','virtualenv','__pycache__','tmp','logs',
          'scripts','tests','wheels','staticfiles'}
    found=[]
    for base in roots:
        if base.is_symlink() or not base.is_dir(): continue
        for current,dirs,files in os.walk(base,followlinks=False):
            dirs[:]=[name for name in dirs if name not in skip and not (Path(current)/name).is_symlink()]
            for name in files:
                path=Path(current)/name
                if path.suffix.lower() not in suffixes or path.is_symlink(): continue
                try:
                    if path.stat().st_size>2_000_000: continue
                    raw=path.read_bytes()
                except OSError: continue
                text=raw.decode('utf-8','ignore')
                if 'id="atelier-original-vector-879"' in text and (OLD_ATELIER_CTA in text or NEW_ATELIER_CTA in text):
                    found.append((path,raw,text))
    if len(found)!=1:
        labels=[str(row[0]) for row in found]
        fail('Expected one source for the public Atelier card; matches='+json.dumps(labels))
    path,raw,text=found[0]
    if text.count('id="atelier-original-vector-879"')!=1:
        fail('Atelier source does not have one unique card marker')
    return path,raw,text

def patch_atelier(source):
    if source.count('id="atelier-original-vector-879"')!=1:
        fail('Atelier card anchor changed')
    if source.count(OLD_ATELIER_CTA)==1 and source.count(NEW_ATELIER_CTA)==0:
        return source.replace(OLD_ATELIER_CTA,NEW_ATELIER_CTA,1)
    if source.count(OLD_ATELIER_CTA)==0 and source.count(NEW_ATELIER_CTA)==1:
        return source
    fail('Expected one accurate or one legacy Atelier TRX CTA')

def product_template_patch(source):
    if OLD_PRODUCT_PAYMENT not in source and source.count('secure order-specific TRX invoice')==1:
        return source
    if source.count(OLD_PRODUCT_PAYMENT)!=1:
        fail('Expected one unsupported ETH/TRX claim in the product detail template')
    return source.replace(OLD_PRODUCT_PAYMENT,'TRX',1)

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

def publish(run):
    if (ROOT.is_symlink() or not ROOT.is_dir() or STORE.is_symlink() or not STORE.is_file()
        or PRODUCT_TEMPLATE.is_symlink() or not PRODUCT_TEMPLATE.is_file()):
        fail('Unexpected checkout root or product template')
    if not (ROOT/'manage.py').is_file(): fail('Django app root is incomplete')
    old=STORE.read_bytes()
    text=old.decode('utf-8')
    new=transform(text).encode('utf-8')
    old_product=PRODUCT_TEMPLATE.read_bytes()
    new_product=product_template_patch(old_product.decode('utf-8')).encode('utf-8')
    atelier_path,old_atelier,atelier_text=find_atelier_source()
    new_atelier=patch_atelier(atelier_text).encode('utf-8')
    verify_products()
    if new==old and new_product==old_product and new_atelier==old_atelier:
        print('MPW_THREE_PRODUCT_CATALOG_RELEASE='+json.dumps({
            'run':run,'products':list(EXPECTED),'already_current':True,
            'private_files_ready':True},sort_keys=True))
        return
    backup=backup_path(run)
    product_backup=backup.with_suffix('.product.bak')
    atelier_backup=backup.with_suffix('.atelier.bak')
    if any(p.exists() or p.is_symlink() for p in (backup,product_backup,atelier_backup)):
        fail('Release backup already exists')
    with backup.open('xb') as f:
        os.fchmod(f.fileno(),0o600); f.write(old); f.flush(); os.fsync(f.fileno())
    with product_backup.open('xb') as f:
        os.fchmod(f.fileno(),0o600); f.write(old_product); f.flush(); os.fsync(f.fileno())
    with atelier_backup.open('xb') as f:
        os.fchmod(f.fileno(),0o600); f.write(old_atelier); f.flush(); os.fsync(f.fileno())
    try:
        if digest(STORE.read_bytes())!=digest(old): fail('Concurrent template update detected')
        if digest(PRODUCT_TEMPLATE.read_bytes())!=digest(old_product): fail('Concurrent product detail template update detected')
        if atelier_path.is_symlink() or digest(atelier_path.read_bytes())!=digest(old_atelier): fail('Concurrent Atelier card source update detected')
        atomic(STORE,new)
        atomic(PRODUCT_TEMPLATE,new_product)
        atomic(atelier_path,new_atelier)
        written=STORE.read_text('utf-8')
        if written.count(NEW_CHECKOUT)!=2 or 'mpw-crypto-buy' in written:
            fail('Bounded two-book source verification failed')
        if 'ETH/TRX' in PRODUCT_TEMPLATE.read_text('utf-8'):
            fail('Third product still claims ETH support')
        if NEW_ATELIER_CTA not in atelier_path.read_text('utf-8') or OLD_ATELIER_CTA in atelier_path.read_text('utf-8'):
            fail('Public Atelier card CTA remains inaccurate')
        print('MPW_THREE_PRODUCT_CATALOG_RELEASE='+json.dumps({
            'run':run,'products':list(EXPECTED),'book_trx_ctas':2,
            'third_product_eth_claim_removed':True,'legacy_book_ctas_removed':True,
            'atelier_source':str(atelier_path),
            'private_files_ready':True,'store_before_sha256':digest(old),
            'store_after_sha256':digest(new),'product_before_sha256':digest(old_product),
            'product_after_sha256':digest(new_product),'atelier_before_sha256':digest(old_atelier),
            'atelier_after_sha256':digest(new_atelier)},sort_keys=True))
    except BaseException:
        if STORE.exists() and digest(STORE.read_bytes())==digest(new): atomic(STORE,old)
        if PRODUCT_TEMPLATE.exists() and digest(PRODUCT_TEMPLATE.read_bytes())==digest(new_product):
            atomic(PRODUCT_TEMPLATE,old_product)
        if atelier_path.exists() and digest(atelier_path.read_bytes())==digest(new_atelier):
            atomic(atelier_path,old_atelier)
        raise

def rollback(run):
    backup=backup_path(run)
    if backup.is_symlink() or not backup.is_file(): fail('Release backup missing')
    old=backup.read_bytes()
    if STORE.is_symlink() or not STORE.is_file(): fail('Unsafe storefront template')
    current=STORE.read_bytes()
    product_backup=backup.with_suffix('.product.bak')
    if product_backup.is_symlink() or not product_backup.is_file(): fail('Product template backup missing')
    old_product=product_backup.read_bytes()
    atelier_backup=backup.with_suffix('.atelier.bak')
    if atelier_backup.is_symlink() or not atelier_backup.is_file(): fail('Atelier card source backup missing')
    old_atelier=atelier_backup.read_bytes()
    atelier_path,_,atelier_text=find_atelier_source()
    if (transform(old.decode('utf-8')).encode('utf-8')!=current
        or product_template_patch(old_product.decode('utf-8')).encode('utf-8')!=PRODUCT_TEMPLATE.read_bytes()
        or patch_atelier(old_atelier.decode('utf-8')).encode('utf-8')!=atelier_path.read_bytes()):
        fail('Storefront changed after release; refusing to overwrite newer edits')
    atomic(STORE,old)
    atomic(PRODUCT_TEMPLATE,old_product)
    atomic(atelier_path,old_atelier)
    print('MPW_THREE_PRODUCT_CATALOG_ROLLBACK='+json.dumps({'restored':True,'store_sha256':digest(old),'product_sha256':digest(old_product)},sort_keys=True))

def selftest():
    s=START+'\n'+OLD_INTRO+'\n'+OLD_STATUS*2+'\n'+OLD_CHECKOUT*2+'\n'
    s+='\n'.join(OLD_BUY.values())+'\n'
    s+='/store/product/72/checkout/\n'
    s+='id="mpw-sale-book72" id="mpw-sale-book225"\n'+END
    out=transform(s)
    assert out.count('Buy securely with TRX ↗')==2
    assert 'ETH/TRX' not in out and 'ETH / TRX' not in out and 'mpw-crypto-buy' not in out
    assert transform(out)==out
    card='id="atelier-original-vector-879" '+OLD_ATELIER_CTA
    assert NEW_ATELIER_CTA in patch_atelier(card)
    assert patch_atelier('id="atelier-original-vector-879" '+NEW_ATELIER_CTA)==('id="atelier-original-vector-879" '+NEW_ATELIER_CTA)
    print('MPW_THREE_PRODUCT_CATALOG_SELFTEST=PASS')

if __name__=='__main__':
    if len(sys.argv)==2 and sys.argv[1]=='selftest': selftest()
    elif len(sys.argv)==3 and sys.argv[1]=='publish': publish(sys.argv[2])
    elif len(sys.argv)==3 and sys.argv[1]=='rollback': rollback(sys.argv[2])
    else: raise SystemExit('Usage: selftest | publish|rollback RUN_ID')
