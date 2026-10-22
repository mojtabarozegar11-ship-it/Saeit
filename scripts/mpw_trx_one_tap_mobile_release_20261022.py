#!/usr/bin/env python3
"""TRX-first checkout with official one-tap TronLink DApp launcher, guarded reversible template patch.
Never bypasses wallet consent, invoice verification, ledger, entitlement, or private file checks.
"""
import hashlib,json,os,pwd,re,stat,sys,tempfile
from pathlib import Path
APP=Path('/home/zomorod2/Saeit-staging')
SITE=Path('/home/zomorod2/mojplaywin.com')
TARGET=APP/'mpw_commerce/templates/mpw_commerce/product_checkout.html'
BACKUPS=Path('/home/zomorod2/.private_mojplaywin_main_agents')
MARK='MPW_TRX_ONE_TAP_DAPP_V1'
PIN='349348bc62c1c85e8642c3fde21801ea5875dd37bf23ef93f0f5eca52c2c9f35'
PICK='<option value="TRX">TRON mainnet · TRX</option>'
BUTTON='<button id="start" type="button">Connect wallet and request an invoice</button>'
CTA='''<!-- MPW_TRX_ONE_TAP_DAPP_V1 -->
<p class="mpw-tronlink-launch">
 <a id="mpw-tronlink-open" href="#" rel="noopener noreferrer">Open checkout in TronLink (TRX) - one tap</a>
 <small>Opens the wallet DApp browser. You must personally approve any payment. No funds move by opening this link.</small>
</p>'''
ANCHOR='const productId = {{ product.pk }};'
JS='''
// MPW_TRX_ONE_TAP_DAPP_V1: official TronLink "open DApp" link from verified merchant URL.
const tronLinkOpen=document.getElementById("mpw-tronlink-open");
const checkoutUrl="https://mojplaywin.com/store/product/"+productId+"/checkout/";
const tronLinkParam={url:checkoutUrl,action:"open",protocol:"TronLink",version:"1.0"};
tronLinkOpen.href="tronlinkoutside://pull.activity?param="+encodeURIComponent(JSON.stringify(tronLinkParam));
'''
CSS='''
/* MPW_TRX_ONE_TAP_DAPP_V1 */
.mpw-tronlink-launch{margin:12px 0 18px;max-width:100%}
.mpw-tronlink-launch a{display:block;max-width:100%;padding:15px 17px;border-radius:13px;
background:linear-gradient(110deg,#66e3ce,#80baff);color:#07192b;font-weight:800;
text-align:center;text-decoration:none;overflow-wrap:anywhere}
.mpw-tronlink-launch small{display:block;margin:8px 3px;color:#e2e7ef;line-height:1.5}
'''
def sha(b):return hashlib.sha256(b).hexdigest()
def fail(s):raise RuntimeError(s)
def guard():
 if pwd.getpwuid(os.getuid()).pw_name!='zomorod2':fail('Unexpected cPanel identity')
 for p in (APP,SITE,TARGET,BACKUPS,TARGET.parent):
  if p.is_symlink() or not p.exists():fail('Unsafe checkout path')
 if not TARGET.is_file() or not BACKUPS.is_dir() or stat.S_IMODE(BACKUPS.stat().st_mode)&0o077:
  fail('Missing checkout or private backups')
 w=SITE/'passenger_wsgi.py'
 if w.is_symlink() or "APP='/home/zomorod2/Saeit-staging'" not in w.read_text('utf8','replace'):fail('Wrong Passenger route')
def one(s,a,b):
 if s.count(a)!=1:fail('Unexpected checkout template revision')
 return s.replace(a,b,1)
def transform(blob):
 if sha(blob)!=PIN:fail('Checkout changed since last verified release; do not overwrite')
 s=blob.decode('utf8')
 if MARK in s:fail('Already installed')
 if s.count('</style>')!=2 or s.count('<script')!=1 or s.count('</script>')!=1 or s.count('{% csrf_token %}')!=1:
  fail('Changed CSP or CSRF')
 s=one(s,PICK,'<option value="TRX" selected>TRON mainnet · TRX</option>')
 s=one(s,BUTTON,BUTTON+'\n'+CTA)
 s=one(s,ANCHOR,ANCHOR+'\n'+JS)
 s=s.replace('</style>',CSS+'</style>',1)
 if s.count(MARK)!=3:fail('Unexpected link, script or CSS patch')
 for token in ('/commerce/checkout/order/','/commerce/checkout/challenge/','/commerce/checkout/verify/',
               '/commerce/checkout/invoice/','/commerce/checkout/status/','{% csrf_token %}'):
  if s.count(token)!=blob.decode('utf8').count(token):fail('Financial/security contract changed')
 if s.count('<script')!=1 or s.count('<style')!=2:fail('Unexpected script/style change')
 return s.encode('utf8')
def contract(blob):
 os.chdir(APP);sys.path.insert(0,str(APP));os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
 import django;django.setup()
 from django.template import Template,RequestContext
 from django.test import RequestFactory
 from django.http import HttpResponse
 from types import SimpleNamespace
 from core.models import Product
 from mpw_commerce.product_checkout_page import _apply_two_book_strict_csp
 tpl=Template(blob.decode('utf8'))
 for pk in (72,225,779,879):
  req=RequestFactory().get('/store/product/%d/checkout/'%pk,secure=True,HTTP_HOST='mojplaywin.com')
  req.user=SimpleNamespace(is_authenticated=True,is_active=True,pk=-83839)
  html=tpl.render(RequestContext(req,{'product':Product.objects.get(pk=pk),'price_usd':'0.03'}))
  resp=_apply_two_book_strict_csp(HttpResponse(html))
  if resp.status_code!=200 or ('Content-Security-Policy' not in html and not resp.has_header('Content-Security-Policy')):
   fail('Strict CSP failed')
  if html.count('id="mpw-tronlink-open"')!=1 or 'value="TRX" selected' not in html:fail('One-tap link missing')
 print('MPW_TRX_ONE_TAP_DJANGO_CSP_4_PRODUCTS=PASS')
def paths(run):
 if not re.fullmatch(r'\d{8,20}',run):fail('Invalid run ID')
 return BACKUPS/('mpw-trx-tap-'+run+'.bak'),BACKUPS/('mpw-trx-tap-'+run+'.json')
def atomic(blob):
 fd,p=tempfile.mkstemp(dir=TARGET.parent,prefix='.mpw-trx-tap-')
 try:
  os.fchmod(fd,stat.S_IMODE(TARGET.stat().st_mode))
  with os.fdopen(fd,'wb') as f:f.write(blob);f.flush();os.fsync(f.fileno())
  os.replace(p,TARGET)
 finally:
  if os.path.exists(p):os.unlink(p)
def preview():
 guard();old=TARGET.read_bytes();new=transform(old);contract(new)
 print('MPW_TRX_ONE_TAP_PREFLIGHT='+json.dumps({'old':sha(old),'new':sha(new),'only_html_template':True,'money_moved':False}))
def publish(run):
 guard();old=TARGET.read_bytes();new=transform(old);contract(new)
 backup,manifest=paths(run)
 if any(p.exists() or p.is_symlink() for p in (backup,manifest)):fail('Backup collision')
 with backup.open('xb') as f:os.fchmod(f.fileno(),0o600);f.write(old);f.flush();os.fsync(f.fileno())
 payload={'run':run,'old':sha(old),'new':sha(new)}
 with manifest.open('x') as f:os.fchmod(f.fileno(),0o600);json.dump(payload,f);f.flush();os.fsync(f.fileno())
 if sha(TARGET.read_bytes())!=payload['old']:fail('Concurrent template update')
 atomic(new)
 if sha(TARGET.read_bytes())!=payload['new']:fail('Post-write checksum mismatch')
 print('MPW_TRX_ONE_TAP_PUBLISHED=PASS; FINANCIAL_WRITES=0')
def verify(run):
 guard();backup,manifest=paths(run)
 if any(p.is_symlink() or not p.is_file() for p in (backup,manifest)):fail('Missing backup')
 data=json.loads(manifest.read_text('utf8'))
 if data['run']!=run or sha(backup.read_bytes())!=data['old'] or sha(TARGET.read_bytes())!=data['new']:
  fail('Deployed hash mismatch')
 contract(TARGET.read_bytes())
 print('MPW_TRX_ONE_TAP_VERIFIED=PASS')
def rollback(run):
 guard();backup,manifest=paths(run)
 if any(p.is_symlink() or not p.is_file() for p in (backup,manifest)):fail('Missing rollback')
 item=json.loads(manifest.read_text('utf8'));old=backup.read_bytes()
 if item['run']!=run or sha(old)!=item['old'] or sha(TARGET.read_bytes())!=item['new']:fail('Concurrent edit; refuse rollback')
 atomic(old);print('MPW_TRX_ONE_TAP_ROLLBACK=PASS')
def emit_js():
 guard();s=transform(TARGET.read_bytes()).decode('utf8')
 arr=re.findall(r'<script\b[^>]*>(.*?)</script\s*>',s,re.I|re.S)
 if len(arr)!=1:fail('Unexpected script count')
 out=arr[0].replace('{{ product.pk }}','779')
 if '{{' in out or '{%' in out:fail('Unresolved JS Django expression')
 print(out)
def selftest():
 assert 'tronlinkoutside://pull.activity?param=' in JS
 assert 'action:"open"' in JS and 'version:"1.0"' in JS
 assert 'personally approve any payment' in CTA
 print('MPW_TRX_ONE_TAP_SELFTEST=PASS')
if __name__=='__main__':
 if len(sys.argv)==2 and sys.argv[1] in ('selftest','preview','emit_js'):globals()[sys.argv[1]]()
 elif len(sys.argv)==3 and sys.argv[1] in ('publish','verify','rollback'):globals()[sys.argv[1]](sys.argv[2])
 else:raise SystemExit('selftest|preview|emit_js|publish RUN|verify RUN|rollback RUN')
