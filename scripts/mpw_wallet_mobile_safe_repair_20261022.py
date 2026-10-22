#!/usr/bin/env python3
"""Surgical reversible mobile wallet fallback for live MojPlayWin checkout.

Patches only one HTML template, never touches payment, signature backend, database,
wallet destinations or saved keys. Missing injected providers remain fail-closed.
"""
import hashlib,json,os,pwd,re,stat,sys,tempfile
from pathlib import Path

APP=Path('/home/zomorod2/Saeit-staging')
SITE=Path('/home/zomorod2/mojplaywin.com')
TARGET=APP/'mpw_commerce/templates/mpw_commerce/product_checkout.html'
BACKUPS=Path('/home/zomorod2/.private_mojplaywin_main_agents')
MARK='MPW_WALLET_MOBILE_RECOVERY_20261022'
CSS_ANCHOR='</style>'
STATUS_ANCHOR='<p id="status" role="status" aria-live="polite"></p>'
START_ANCHOR='const status = document.getElementById("status");'
CATCH_ANCHOR='''  } catch(err) {
    say(err instanceof Error ? err.message : "Checkout failed. Do NOT send any funds.");
  } finally {start.disabled=false;}'''
OLD_WALLET='''function readWallet(asset) {
  if (asset==="ETH") {
    if (!window.ethereum || !window.ethereum.request) throw new Error("No compatible Ethereum wallet found. Open this page inside your wallet browser.");
    return window.ethereum.request({method:"eth_requestAccounts"}).then(accounts => {
      if (!accounts || !accounts.length) throw new Error("Wallet connection was declined.");
      return {sender:accounts[0],sign:message=>window.ethereum.request({method:"personal_sign",params:[message,accounts[0]]})};
    });
  }
  const tron = window.tronWeb;
  if (!tron || !tron.defaultAddress || !tron.defaultAddress.base58 || !tron.trx || !tron.trx.signMessageV2) {
    throw new Error("No compatible TRON wallet signer is available. Use a TRON wallet browser.");
  }
  return Promise.resolve({sender:tron.defaultAddress.base58,sign:message=>tron.trx.signMessageV2(message)});
}'''
NEW_WALLET='''function walletUnavailable(asset) {
  const err=new Error(asset==="TRX"
    ? "TRON wallet not detected in this browser. Open this exact checkout page in the TronLink DApp browser (Discover)."
    : "Ethereum wallet not detected in this browser. Open checkout inside MetaMask's mobile browser.");
  err.name="WalletUnavailable";
  return err;
}
async function readWallet(asset) {
  if (asset==="ETH") {
    const provider=window.ethereum;
    if (!provider || typeof provider.request!=="function") throw walletUnavailable("ETH");
    const accounts=await provider.request({method:"eth_requestAccounts"});
    if (!Array.isArray(accounts) || !accounts.length) throw new Error("Wallet connection was declined.");
    const sender=accounts[0];
    return {sender,sign:message=>provider.request({method:"personal_sign",params:[message,sender]})};
  }
  // TronLink's modern interface is window.tron, legacy DApp providers inject window.tronWeb.
  const provider=window.tron;
  let tron=(provider && provider.tronWeb) || window.tronWeb;
  if ((!tron || !tron.defaultAddress || !tron.defaultAddress.base58) &&
      provider && typeof provider.request==="function") {
    await provider.request({method:"eth_requestAccounts"});
    tron=provider.tronWeb || window.tronWeb;
  }
  if (!tron || !tron.defaultAddress || !tron.defaultAddress.base58 ||
      !tron.trx || typeof tron.trx.signMessageV2!=="function") {
    throw walletUnavailable("TRX");
  }
  return {sender:tron.defaultAddress.base58,sign:message=>tron.trx.signMessageV2(message)};
}'''
CSS=r'''
/* MPW_WALLET_MOBILE_RECOVERY_20261022: prevent RTL machine-translation overflow */
main,main *,main *::before,main *::after{min-width:0;max-width:100%}
main p,main a,main label,main strong,main button,main #status{
 overflow-wrap:anywhere;word-break:normal;white-space:normal}
main button{max-width:100%;line-height:1.45}
.mpw-wallet-help{border:1px solid #7fabc6;border-radius:12px;padding:14px;
 margin:12px 0 18px;background:#142a3b;color:#ecf6ff;line-height:1.65}
.mpw-wallet-help[hidden]{display:none}
.mpw-wallet-help p{margin:8px 0}
.mpw-wallet-help a{display:inline-block;max-width:100%;overflow-wrap:anywhere}
@media(max-width:600px){
 body{padding:10px}
 main{width:100%;padding:15px;margin:10px auto;border-radius:14px}
 main p,main label,main strong{font-size:clamp(15px,4vw,19px);line-height:1.65}
 main button,main select{font-size:clamp(15px,4vw,19px);width:100%;margin:10px 0 0}
 .panel{padding:12px;margin:12px 0}
}
'''
HELP='''<!-- MPW_WALLET_MOBILE_RECOVERY_20261022 -->
<section id="mpw-wallet-help" class="mpw-wallet-help" hidden role="status" aria-live="polite">
 <strong>Wallet connection on a phone</strong>
 <p id="mpw-wallet-advice">Your current browser cannot access the selected wallet signer.</p>
 <p>For TRX: open TronLink, choose Discover / DApp browser, and visit the same checkout address.
 For ETH: open this checkout in the MetaMask mobile browser.</p>
 <p><a id="mpw-eth-wallet-open" rel="noopener noreferrer"
 href="https://link.metamask.io/dapp/mojplaywin.com/store/product/{{ product.pk }}/checkout/">
 Open this ETH checkout in MetaMask</a></p>
 <button id="mpw-copy-checkout" type="button">Copy checkout address for wallet browser</button>
 <p>Log in again inside the wallet browser if needed. No invoice is created and no money is
 sent just by opening this page. Never share a recovery phrase or private key.</p>
</section>'''
JS_STATE='''const walletHelp=document.getElementById("mpw-wallet-help");
const walletAdvice=document.getElementById("mpw-wallet-advice");
const walletEthLink=document.getElementById("mpw-eth-wallet-open");
const copyCheckout=document.getElementById("mpw-copy-checkout");
copyCheckout.addEventListener("click",async()=>{
  try {
    if (!navigator.clipboard || typeof navigator.clipboard.writeText!=="function")
      throw new Error("Clipboard is unavailable.");
    await navigator.clipboard.writeText("https://mojplaywin.com/store/product/"+productId+"/checkout/");
    copyCheckout.textContent="Checkout address copied";
  } catch(err) {
    copyCheckout.textContent="Copy from your browser address bar";
  }
});
'''
NEW_CATCH='''  } catch(err) {
    if (err && err.name==="WalletUnavailable") {
      const asset=document.getElementById("asset").value;
      walletAdvice.textContent=err.message;
      walletEthLink.hidden=(asset!=="ETH");
      walletHelp.hidden=false;
    }
    say(err instanceof Error ? err.message : "Checkout failed. Do NOT send any funds.");
  } finally {start.disabled=false;}'''

def digest(data):return hashlib.sha256(data).hexdigest()
def fail(msg):raise RuntimeError(msg)

def guard():
 if pwd.getpwuid(os.getuid()).pw_name!='zomorod2':fail('Unexpected host user')
 for p in (APP,SITE,BACKUPS,TARGET,TARGET.parent):
  if p.is_symlink() or not p.exists():fail('Unsafe site path')
 if not TARGET.is_file() or not BACKUPS.is_dir():fail('Missing required checkout file')
 if stat.S_IMODE(BACKUPS.stat().st_mode)&0o077:fail('Backup directory permissions unsafe')
 w=SITE/'passenger_wsgi.py'
 if w.is_symlink() or "APP='/home/zomorod2/Saeit-staging'" not in w.read_text('utf8','replace'):fail('Wrong Passenger target')

def replace_one(text,old,new):
 if text.count(old)!=1:fail('Template version drift; expected exact source anchor')
 return text.replace(old,new,1)

def transform(original):
 s=original.decode('utf8')
 if MARK in s:fail('Mobile recovery already installed')
 if not 6000<len(s)<100000 or s.count('<script')!=1 or s.count('</script>')!=1 or s.count('<style')!=2:fail('Unexpected checkout HTML')
 if s.count('{% csrf_token %}')!=1:fail('CSRF contract drift')
 s=replace_one(s,CSS_ANCHOR,CSS+CSS_ANCHOR)
 s=replace_one(s,STATUS_ANCHOR,STATUS_ANCHOR+'\n'+HELP)
 s=replace_one(s,START_ANCHOR,START_ANCHOR+'\n'+JS_STATE)
 s=replace_one(s,OLD_WALLET,NEW_WALLET)
 s=replace_one(s,CATCH_ANCHOR,NEW_CATCH)
 if s.count(MARK)!=2:fail('Missing DOM or CSS patch')
 for marker in ('/commerce/checkout/order/','/commerce/checkout/challenge/',
  '/commerce/checkout/verify/','/commerce/checkout/invoice/','/commerce/checkout/status/',
  'can_access_purchased_items','{% csrf_token %}'):
  if s.count(marker)!=original.decode('utf8').count(marker):fail('Financial or security contract altered')
 if s.count('<script')!=1 or s.count('</script>')!=1 or s.count('<style')!=2:fail('Unexpected script/style count')
 return s.encode('utf8')

def contract(data):
 os.chdir(APP);sys.path.insert(0,str(APP))
 os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
 import django;django.setup()
 from django.template import Template, RequestContext
 from django.test import RequestFactory
 from django.http import HttpResponse
 from core.models import Product
 from mpw_commerce.product_checkout_page import _apply_two_book_strict_csp
 from types import SimpleNamespace
 tpl=Template(data.decode('utf8'))
 for product_id in (72,225,779,879):
  req=RequestFactory().get('/commerce/book/%d/'%product_id,secure=True,HTTP_HOST='mojplaywin.com')
  req.user=SimpleNamespace(is_authenticated=True,is_active=True,pk=-921000)
  ctx=RequestContext(req,{'product':Product.objects.get(pk=product_id),'price_usd':'1.00'})
  html=tpl.render(ctx)
  resp=_apply_two_book_strict_csp(HttpResponse(html))
  body=resp.content.decode('utf8','replace')
  if resp.status_code!=200 or 'MPW_WALLET_MOBILE_RECOVERY_20261022' not in body or 'walletUnavailable' not in body:
   fail('Synthetic signed-in checkout render failed')
  if 'Content-Security-Policy' not in body and not resp.has_header('Content-Security-Policy'):
   fail('Strict CSP not preserved')
 print('MPW_WALLET_MOBILE_DJANGO_CSP_CONTRACT=PASS; PAYMENT_WRITES=0')

def paths(run):
 if not re.fullmatch(r'[0-9]{8,20}',run):fail('Invalid run id')
 return BACKUPS/('mpw-mobile-wallet-'+run+'.bak'),BACKUPS/('mpw-mobile-wallet-'+run+'.json')

def atomic(data):
 fd,path=tempfile.mkstemp(dir=TARGET.parent,prefix='.mpw-wallet-mobile-')
 try:
  os.fchmod(fd,stat.S_IMODE(TARGET.stat().st_mode))
  with os.fdopen(fd,'wb') as file:
   file.write(data);file.flush();os.fsync(file.fileno())
  os.replace(path,TARGET)
 finally:
  if os.path.exists(path):os.unlink(path)

def preview():
 guard();old=TARGET.read_bytes();new=transform(old);contract(new)
 print('MPW_WALLET_MOBILE_PREVIEW='+json.dumps({'old_sha256':digest(old),'new_sha256':digest(new),'file':'mpw_commerce/templates/mpw_commerce/product_checkout.html','financial_writes':0}))

def publish(run):
 guard();old=TARGET.read_bytes();new=transform(old);contract(new)
 backup,manifest=paths(run)
 if backup.exists() or manifest.exists() or backup.is_symlink() or manifest.is_symlink():fail('Existing backup')
 with backup.open('xb') as f:
  os.fchmod(f.fileno(),0o600);f.write(old);f.flush();os.fsync(f.fileno())
 payload={'run':run,'old':digest(old),'new':digest(new)}
 with manifest.open('x',encoding='utf8') as f:
  os.fchmod(f.fileno(),0o600);json.dump(payload,f);f.flush();os.fsync(f.fileno())
 if digest(TARGET.read_bytes())!=payload['old']:fail('Concurrent update, no write')
 atomic(new)
 if digest(TARGET.read_bytes())!=payload['new']:fail('Write mismatch')
 print('MPW_WALLET_MOBILE_PUBLISHED=PASS; SITE_FILE_ONLY=1; FINANCIAL_WRITES=0')

def verify(run):
 guard();backup,manifest=paths(run)
 if any(p.is_symlink() or not p.is_file() for p in (backup,manifest)):fail('Missing private backup')
 item=json.loads(manifest.read_text('utf8'))
 if item.get('run')!=run or digest(backup.read_bytes())!=item['old'] or digest(TARGET.read_bytes())!=item['new']:fail('Unexpected deployed revision')
 if digest(transform(backup.read_bytes()))!=item['new']:fail('Unexpected source patch')
 contract(TARGET.read_bytes())
 print('MPW_WALLET_MOBILE_VERIFIED=PASS')

def rollback(run):
 guard();backup,manifest=paths(run)
 if any(p.is_symlink() or not p.is_file() for p in (backup,manifest)):fail('No rollback')
 item=json.loads(manifest.read_text('utf8'));before=backup.read_bytes()
 if item['run']!=run or digest(before)!=item['old'] or digest(TARGET.read_bytes())!=item['new']:fail('Concurrent edit; rollback held')
 atomic(before)
 if digest(TARGET.read_bytes())!=item['old']:fail('Rollback failed')
 print('MPW_WALLET_MOBILE_ROLLBACK=PASS')

def emit_js():
 guard()
 import re
 s=transform(TARGET.read_bytes()).decode('utf8')
 parts=re.findall(r'<script\b[^>]*>(.*?)</script\s*>',s,re.S|re.I)
 if len(parts)!=1:fail('Unexpected script count')
 script=parts[0].replace('{{ product.pk }}','779')
 if '{{' in script or '{%' in script:fail('Unexpected template expression')
 print(script)

def selftest():
 assert 'signMessageV2' in NEW_WALLET and 'eth_requestAccounts' in NEW_WALLET
 assert 'MPW_WALLET_MOBILE_RECOVERY_20261022' in HELP
 for data in (b'old',b'<script>test</script>'):
  try:transform(data)
  except RuntimeError:pass
  else:fail('Drift guard missing')
 print('MPW_WALLET_MOBILE_SELFTEST=PASS')

if __name__=='__main__':
 if len(sys.argv)==2 and sys.argv[1] in ('selftest','preview','emit_js'):
  globals()[sys.argv[1]]()
 elif len(sys.argv)==3 and sys.argv[1] in ('publish','verify','rollback'):
  globals()[sys.argv[1]](sys.argv[2])
 else:raise SystemExit('selftest|preview|emit_js|publish RUN|verify RUN|rollback RUN')
