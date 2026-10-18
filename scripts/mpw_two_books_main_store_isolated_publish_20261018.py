#!/usr/bin/env python3
"""Add exactly two book listings to the live MojPlayWin main store.

Publishes editorial catalog information, NOT payment acceptance. This
touches only core/templates/mojplaywin/store.html and never restarts Passenger,
edits Django models, or modifies protected child site templates.
"""
import hashlib, json, os, re, stat, sys, tempfile
from pathlib import Path

HOME=Path('/home/zomorod2')
APP=HOME/'Saeit-staging'
STORE=APP/'core/templates/mojplaywin/store.html'
WSGI=HOME/'mojplaywin.com/passenger_wsgi.py'
EXPECTED='466dd7a61ebafb97d3f825e50134022092945dcb24c8d53c5411c0e941e64d26'
START='<!-- MPW_TWO_BOOKS_PUBLIC_CATALOG_V1_START -->'
END='<!-- MPW_TWO_BOOKS_PUBLIC_CATALOG_V1_END -->'
ANCHOR='<p class="mw-note">'
SNIPPET='''<!-- MPW_TWO_BOOKS_PUBLIC_CATALOG_V1_START -->
<section class="mpw-two-books" id="mpw-original-books" aria-label="Original MojPlayWin books">
<style>
.mpw-two-books{margin:32px 0 36px;padding:clamp(16px,3vw,32px);border:1px solid rgba(186,204,230,.24);border-radius:26px;background:linear-gradient(145deg,rgba(20,42,69,.64),rgba(18,26,48,.42));box-shadow:0 16px 48px rgba(0,0,0,.15);color:#f3f6fc}
.mpw-two-books .mpw-book-intro{max-width:760px;margin:0 0 22px;color:#d5dfed;line-height:1.75}
.mpw-two-books h2{font-size:clamp(1.5rem,2.4vw,2.1rem);margin:6px 0 14px;color:#fff}
.mpw-two-books .mpw-book-list{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:22px}
.mpw-two-books .mpw-sale-book{min-width:0;display:grid;grid-template-columns:minmax(110px,34%) 1fr;gap:18px;padding:20px;border:1px solid rgba(255,255,255,.17);border-radius:22px;background:linear-gradient(130deg,rgba(255,255,255,.12),rgba(255,255,255,.035));box-shadow:0 10px 22px rgba(0,0,0,.13)}
.mpw-two-books .mpw-book-cover{aspect-ratio:3/4;display:flex;flex-direction:column;justify-content:space-between;gap:12px;padding:18px 14px;border-radius:8px 14px 14px 8px;box-shadow:inset 5px 0 9px rgba(0,0,0,.25),5px 9px 20px rgba(0,0,0,.25);overflow-wrap:anywhere}
.mpw-two-books .mpw-book-cover span{font-size:.71rem;letter-spacing:.12em;text-transform:uppercase;opacity:.85}
.mpw-two-books .mpw-book-cover strong{font-size:clamp(1.0rem,1.6vw,1.5rem);line-height:1.27}
.mpw-two-books .mpw-chess-cover{background:linear-gradient(150deg,#22324d 4%,#455675 48%,#a78b52 100%);color:#fff1ca}
.mpw-two-books .mpw-taniya-cover{background:linear-gradient(155deg,#3b4c87 2%,#7259a7 43%,#edac75 100%);color:#fff7ed}
.mpw-two-books .mpw-book-body{min-width:0}
.mpw-two-books .mpw-book-body h3{font-size:1.16rem;color:#fff;line-height:1.4;margin:5px 0 9px}
.mpw-two-books .mpw-book-body p{font-size:.9rem;line-height:1.65;color:#e0e7f2;margin:8px 0}
.mpw-two-books .mpw-book-meta{font-size:.83rem;color:#c8d7e6}
.mpw-two-books .mpw-book-price{font-weight:750;font-size:1.3rem;color:#f4d99b;margin-top:10px}
.mpw-two-books .mpw-book-state{display:inline-block;color:#f4e4bb;border:1px solid rgba(244,228,187,.5);border-radius:999px;font-size:.76rem;padding:4px 11px}
.mpw-two-books .mpw-book-pay-note{font-size:.83rem;color:#d9e3ef;border-top:1px solid rgba(255,255,255,.18);margin:18px 0 0;padding-top:14px}
@media(max-width:890px){.mpw-two-books .mpw-book-list{grid-template-columns:1fr}}
@media(max-width:480px){.mpw-two-books .mpw-sale-book{grid-template-columns:1fr}.mpw-two-books .mpw-book-cover{aspect-ratio:4/3}}
@media(prefers-reduced-motion:reduce){.mpw-two-books *{animation:none!important;transition:none!important}}
</style>
<span class="mw-kicker">ORIGINAL DIGITAL BOOKS · MOJPLAYWIN</span>
<h2>Books by Mojtaba Roozegar</h2>
<p class="mpw-book-intro">Two original English-language books are listed below with their verified digital editions. Secure purchases will open after the cryptocurrency checkout has passed live settlement and private-delivery checks.</p>
<div class="mpw-book-list">
<article class="mpw-sale-book" id="mpw-sale-book72">
<div class="mpw-book-cover mpw-chess-cover" role="img" aria-label="Typographic cover preview: The Science and Practice of Chess Improvement">
<span>Chess · Research Edition</span><strong>The Science and Practice of Chess Improvement</strong><span>Mojtaba Roozegar · 2026</span>
</div>
<div class="mpw-book-body"><span class="mpw-book-state">Catalog listing · checkout pending</span>
<h3>The Science and Practice of Chess Improvement</h3>
<p>A research-informed training guide on chess decisions, game analysis, strategic understanding, and deliberate practice.</p>
<p class="mpw-book-meta">English · 415 pages · Digital PDF · Grandmaster Analytical Research Edition (2026)</p>
<p class="mpw-book-price">US $7.50</p></div>
</article>
<article class="mpw-sale-book" id="mpw-sale-book225">
<div class="mpw-book-cover mpw-taniya-cover" role="img" aria-label="Typographic cover preview: Taniya and the Little Baker Worms">
<span>Illustrated Story · Ages 3–8</span><strong>Taniya and the Little Baker Worms</strong><span>Mojtaba Roozegar</span>
</div>
<div class="mpw-book-body"><span class="mpw-book-state">Catalog listing · checkout pending</span>
<h3>Taniya and the Little Baker Worms</h3>
<p>An original illustrated children's storybook for young readers and families, created in a colorful landscape-format edition.</p>
<p class="mpw-book-meta">English · 40 pages · Illustrated digital PDF · Suggested ages 3–8</p>
<p class="mpw-book-price">US $4.00</p></div>
</article>
</div>
<p class="mpw-book-pay-note">Payment is not open for these books yet. Please do not send cryptocurrency for an order without a verified checkout invoice. Downloads will be provided privately after confirmed payment once sales are enabled.</p>
</section>
<!-- MPW_TWO_BOOKS_PUBLIC_CATALOG_V1_END -->
'''

def sha(data): return hashlib.sha256(data).hexdigest()
def fail(message): raise RuntimeError(message)
def backup_path(run): return HOME/('.mpw-two-books-store-'+run+'.backup')
def check_id(run):
    if not re.fullmatch(r'[0-9]{9,20}',run):fail('Invalid workflow run identifier')
def check():
    if not APP.is_dir() or APP.is_symlink() or not (APP/'manage.py').is_file():fail('Invalid application root')
    if not WSGI.is_file() or WSGI.is_symlink() or "APP='/home/zomorod2/Saeit-staging'" not in WSGI.read_text('utf8','replace'):fail('Shared Passenger root mismatch')
    if not STORE.is_file() or STORE.is_symlink():fail('Active store template missing or symbolic link')
    old=STORE.read_bytes()
    if sha(old)!=EXPECTED:fail('Active store changed since audited preflight')
    return old

def make(old):
    s=old.decode('utf8')
    if s.count(ANCHOR)!=1 or START in s or END in s:fail('Unexpected insertion target or duplicate publication')
    if not ('id="catalog"' in s and 'store_ten_buyer_guides_20261018.html' in s and '{{ products|length }}' in s):
        fail('Unexpected MojPlayWin main store template')
    if SNIPPET.count('id="mpw-sale-book72"')!=1 or SNIPPET.count('id="mpw-sale-book225"')!=1:fail('Both cards required')
    if any(token in SNIPPET.lower() for token in ('<script','<iframe','<form','wallet-address','checkout/crypto','<a href')):fail('No payment controls or external links in book listing')
    newer=s.replace(ANCHOR,SNIPPET+'\n'+ANCHOR,1).encode('utf8')
    if newer.replace((SNIPPET+'\n'+ANCHOR).encode('utf8'),ANCHOR.encode('utf8'),1)!=old:fail('Nonreversible template change')
    return newer

def write(target,data,mode):
    if target.is_symlink():fail('Unsafe target')
    fd,temp=tempfile.mkstemp(prefix='.mpw-books-publish-',dir=target.parent)
    try:
        os.fchmod(fd,mode)
        with os.fdopen(fd,'wb') as f:
            f.write(data);f.flush();os.fsync(f.fileno())
        os.replace(temp,target)
    finally:
        if os.path.exists(temp):os.unlink(temp)

def verify_books():
    os.chdir(APP);sys.path.insert(0,str(APP));os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
    import django;django.setup()
    from core.models import Product
    from core.cryptopay_checkout import product_delivery_ready
    ids={72:('mojplaywin-chess-improvement-2026','7.50'),225:('mojplaywin-taniya-little-baker-worms','4.00')}
    owners=set()
    for id_,(key,price) in ids.items():
        p=Product.objects.get(pk=id_)
        metadata=p.metadata or {}
        if metadata.get('product_id')!=key or str(p.price)!=price or p.currency!='USD':fail('Catalog identity or price mismatch')
        if not p.owner_id or p.active or metadata.get('checkout_enabled') is not False:fail('Book owner or checkout status changed')
        if not product_delivery_ready(p):fail('Private PDF not deliverable')
        owners.add(p.owner_id)
    if len(owners)!=1:fail('Book authorship mismatch')
    print('BOOKS_LISTING_PRODUCT_GATES=PASS')

def publish(run):
    check_id(run)
    old=check()
    verify_books()
    path=backup_path(run)
    if path.exists() or path.is_symlink():fail('Backup path exists; no overwrite')
    newer=make(old)
    with path.open('xb') as f:
        os.chmod(path,0o600)
        f.write(old);f.flush();os.fsync(f.fileno())
    write(STORE,newer,stat.S_IMODE(STORE.stat().st_mode))
    if sha(STORE.read_bytes())!=sha(newer):fail('Post-publication SHA mismatch')
    print('MPW_TWO_BOOKS_LISTINGS_PUBLISHED='+json.dumps({'ids':[72,225],'store_changed':True,'store_file_only':True,'payment_activated':False,'passenger_restarted':False,'before_sha256':sha(old),'after_sha256':sha(newer)}))

def rollback(run):
    check_id(run)
    path=backup_path(run)
    if path.is_symlink() or not path.is_file():fail('Original backup missing')
    old=path.read_bytes()
    if sha(old)!=EXPECTED:fail('Original backup SHA mismatch')
    current=STORE.read_bytes()
    if START.encode() not in current or END.encode() not in current:fail('Another store change occurred; manual reconciliation required')
    if make(old)!=current:fail('Other changes detected: never overwrite unrelated changes')
    write(STORE,old,stat.S_IMODE(STORE.stat().st_mode))
    print('MPW_TWO_BOOKS_LISTINGS_RESTORED='+json.dumps({'only_store_restored':True,'original_sha256':sha(old)}))

if __name__=='__main__':
    if len(sys.argv)!=3 or sys.argv[1] not in ('publish','rollback'):raise SystemExit('Usage: script.py publish|rollback RUN_ID')
    if sys.argv[1]=='publish':publish(sys.argv[2])
    else:rollback(sys.argv[2])
