#!/usr/bin/env python3
"""MojPlayWin standalone legacy checkout style replacement; no payment code edits."""
import hashlib,json,os,pwd,re,stat,sys,tempfile
from pathlib import Path
HOME=Path('/home/zomorod2')
APP=HOME/'Saeit-staging'
SITE=HOME/'mojplaywin.com'
TARGET=APP/'core/templates/brands/mojplaywin/checkout.html'
BACKUP=HOME/'.private_mojplaywin_main_agents'
CSS=SITE/'mpw-editorial/revenue/assets/mpw-fintech-checkout-v2.css'
PIN='fa4a3f770c3a13a9a543d05d8f16082e9654fda3e53d26d2c968dd3d7ba12e66'
MARK='data-mpw-legacy-checkout="fintech-v2-20261021"'
HTML='''<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<meta name="color-scheme" content="dark">
<title>Checkout | {{ product.title }} | MojPlayWin</title>
<link rel="stylesheet" href="/mpw-editorial/revenue/assets/mpw-fintech-checkout-v2.css?v=20261021">
</head><body><main data-mpw-legacy-checkout="fintech-v2-20261021">
<div class="mpwf-top"><section class="mpwf-intro" aria-label="Checkout overview">
<span class="mpwf-eyebrow">MOJPLAYWIN / DIGITAL CHECKOUT</span>
<div class="mpwf-intro-title">One purchase. A clear next step.</div>
<p class="mpwf-intro-subtitle">Review the item and its listed price, then request payment instructions specific to your own order.</p>
</section><ol class="mpwf-steps" aria-label="Checkout stages">
<li><span class="mpwf-step-num">01</span><span class="mpwf-step-copy">Review product</span></li>
<li><span class="mpwf-step-num">02</span><span class="mpwf-step-copy">Create order</span></li>
<li><span class="mpwf-step-num">03</span><span class="mpwf-step-copy">Verify payment</span></li>
</ol></div>
<section class="panel" aria-labelledby="mpwf-title">
<span class="mpwf-eyebrow">ORDER REVIEW</span>
<h1 id="mpwf-title">{{ product.title }}</h1>
<p class="muted">The payable asset, blockchain network and exact amount must be confirmed by your order-specific invoice.</p>
<p class="price">Listed price: <strong>{{ product.price }} {{ product.currency|default:"USD" }}</strong></p>
<p class="alert" role="note">Never transfer funds to an address or amount from an old page or screenshot. Only use the verified instructions for your own order.</p>
<form method="post">{% csrf_token %}
<button type="submit">Continue to payment instructions →</button>
</form>
<p class="muted">Creating an order is not evidence of payment. Digital delivery follows independent verification.</p>
</section>
<div class="mpwf-footnote"><a href="/store/">← Back to store</a> · <a href="/support/">Support</a> · <a href="/terms/">Terms</a></div>
</main></body></html>'''
def h(raw):return hashlib.sha256(raw).hexdigest()
def fail(message):raise RuntimeError(message)
def guard():
 if pwd.getpwuid(os.getuid()).pw_name!='zomorod2':fail('Wrong host user')
 for p in (APP,SITE,BACKUP):
  if not p.is_dir() or p.is_symlink():fail('Unexpected site path')
 if stat.S_IMODE(BACKUP.stat().st_mode)&0o077:fail('Backup not private')
 for p in (TARGET,CSS,SITE/'passenger_wsgi.py'):
  if not p.is_file() or p.is_symlink():fail('Missing verified file')
 if "APP='/home/zomorod2/Saeit-staging'" not in (SITE/'passenger_wsgi.py').read_text():fail('Wrong Passenger application')
def changed(raw,pinned=True):
 if pinned and h(raw)!=PIN:fail('Live legacy checkout version changed')
 s=raw.decode('utf8')
 if MARK in s:fail('Already styled')
 for v in ('<form method="post">','{% csrf_token %}','{{ product.title }}','{{ product.price }}','12 USDT'):
  if s.count(v)!=1:fail('Legacy checkout contract drifted: '+v)
 for v in ('<form method="post">','{% csrf_token %}','{{ product.title }}','{{ product.price }}'):
  if HTML.count(v)!=1:fail('New checkout contract invalid: '+v)
 if '12 USDT' in HTML:fail('Hardcoded price retained')
 return HTML.encode('utf8')
def render_test(blob):
 os.chdir(APP);sys.path.insert(0,str(APP))
 os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
 import django;django.setup()
 from django.template import Template,Context
 from types import SimpleNamespace
 for price in ('7.50','4.00','0.03'):
  text=Template(blob.decode()).render(Context({'product':SimpleNamespace(title='Sample',price=price,currency='USD')}))
  if MARK not in text or price not in text or '12 USDT' in text or '<form method="post">' not in text:
   fail('Django rendering mismatch')
def stamps(run):
 if not re.fullmatch(r'[0-9]{8,20}',run):fail('Invalid release ID')
 return BACKUP/('mpwf-legacy-v2-'+run+'.bak'),BACKUP/('mpwf-legacy-v2-'+run+'.json')
def atomic(blob):
 fd,path=tempfile.mkstemp(dir=TARGET.parent,prefix='.mpwf-legacy-')
 try:
  os.fchmod(fd,stat.S_IMODE(TARGET.stat().st_mode))
  with os.fdopen(fd,'wb') as f:f.write(blob);f.flush();os.fsync(f.fileno())
  os.replace(path,TARGET)
 finally:
  if os.path.exists(path):os.unlink(path)
def preview():
 guard();old=TARGET.read_bytes();new=changed(old);render_test(new)
 print('MPWF_LEGACY_PREFLIGHT='+json.dumps({'old':h(old),'new':h(new),'security_form_preserved':True,'static_usdt_amount_removed':True}))
def publish(run):
 preview();old=TARGET.read_bytes();new=changed(old);b,m=stamps(run)
 if any(p.exists() or p.is_symlink() for p in (b,m)):fail('Backup collision')
 with b.open('xb') as f:os.fchmod(f.fileno(),0o600);f.write(old);f.flush();os.fsync(f.fileno())
 with m.open('x',encoding='utf8') as f:
  os.fchmod(f.fileno(),0o600);json.dump({'run':run,'before':h(old),'after':h(new)},f)
 if TARGET.read_bytes()!=old:fail('Concurrent checkout modification')
 atomic(new)
 if h(TARGET.read_bytes())!=h(new):fail('Failed checkout hash verification')
 print('MPWF_LEGACY_PUBLISHED='+json.dumps({'run':run,'template_only':True,'payment_backend_changed':False}))
def verify(run):
 guard();b,m=stamps(run);d=json.loads(m.read_text());old=b.read_bytes()
 if d['run']!=run or h(old)!=d['before'] or h(changed(old))!=d['after'] or h(TARGET.read_bytes())!=d['after']:
  fail('Legacy checkout release hash mismatch')
 render_test(TARGET.read_bytes())
 print('MPWF_LEGACY_VERIFIED='+json.dumps({'price_examples':['7.50','4.00','0.03'],'form_csrf_preserved':True,'no_payment_tested':True}))
def rollback(run):
 guard();b,m=stamps(run);d=json.loads(m.read_text());old=b.read_bytes()
 if h(old)!=d['before'] or h(TARGET.read_bytes())!=d['after']:fail('Concurrent change blocks rollback')
 atomic(old);print('MPWF_LEGACY_ROLLBACK=PASS')
def selftest():
 sample=b'<h1>{{ product.title }}</h1><p>{{ product.price }} USD 12 USDT</p><form method="post">{% csrf_token %}</form>'
 assert MARK.encode() in changed(sample,pinned=False)
 print('MPWF_LEGACY_SELFTEST=PASS')
if __name__=='__main__':
 if len(sys.argv)==2 and sys.argv[1] in ('selftest','preview'):
  {'selftest':selftest,'preview':preview}[sys.argv[1]]()
 elif len(sys.argv)==3 and sys.argv[1] in ('publish','verify','rollback'):
  {'publish':publish,'verify':verify,'rollback':rollback}[sys.argv[1]](sys.argv[2])
 else:raise SystemExit('selftest | preview|publish|verify|rollback RUN_ID')
