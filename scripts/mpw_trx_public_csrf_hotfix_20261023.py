"""Align public TRX checkout's HTTP and HTML referrer policies with CSRF."""
import os,pwd,stat,sys,tempfile
from pathlib import Path

APP=Path('/home/zomorod2/Saeit-staging')
PUBLIC=Path('/home/zomorod2/mojplaywin.com')
BACKUP_ROOT=Path('/home/zomorod2/.local/share/mpw-trx-rollbacks')
WEB_REL='services/mpw_trx_commercial_web.py'
PAGES_REL='services/mpw_trx_public_pages.py'
INVOICE_REL='services/mpw_trx_walletless_checkout_ui.py'
OLD_POLICY=b'response["Referrer-Policy"]="no-referrer"'
NEW_POLICY=b'response["Referrer-Policy"]="same-origin"'
HELPER=b'''\ndef _checkout_csrf_referrer(response):
    """Permit HTTPS same-origin Referer while suppressing cross-origin referrers."""
    import re
    content,count=re.subn(
        rb'<meta\\s+name=["\\']referrer["\\']\\s+content=["\\']no-referrer["\\']\\s*/?>',
        b'<meta name="referrer" content="same-origin">',
        response.content,count=1,flags=re.I)
    if count!=1:
        raise Http404("Secure checkout referrer policy is missing or ambiguous")
    response.content=content
    response["Referrer-Policy"]="same-origin"
    return response

'''
META_ANCHOR=b'\n\ndef _page(title, content):\n'
CSP_LINE=b'''    response['Content-Security-Policy']="default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; script-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none"'''
# Keep the original CSP literal intact; this anchor must appear once in the
# product-checkout view and nowhere else in the public pages module.
CSP_LINE=b'''    response['Content-Security-Policy']="default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; script-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'"'''
CALL=b'    response=_checkout_csrf_referrer(response)\n'
MARK='MPW_PUBLIC_TRX_CUSTOMERS_20261023'

def put(path,data):
    if path.is_symlink(): raise RuntimeError('Refuse symlink target')
    tmp=path.with_name(path.name+'.csrf-hotfix-tmp')
    if tmp.exists() or tmp.is_symlink(): raise RuntimeError('Concurrent hotfix detected')
    tmp.write_bytes(data);os.chmod(tmp,stat.S_IMODE(path.stat().st_mode));os.replace(tmp,path)

def run_python(code):
    import subprocess
    py=APP.parent/'virtualenv'/'Saeit-staging'/'3.11'/'bin'/'python'
    return subprocess.run([str(py),'-B','-c',code],cwd=APP,capture_output=True,text=True,timeout=40)

def verify_runtime():
    code='''import os\nos.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")\nimport django;django.setup()\nfrom django.http import HttpResponse\nfrom services.mpw_trx_commercial_web import _nocache\nfrom services.mpw_trx_public_pages import _checkout_csrf_referrer\nr=_nocache(HttpResponse("<meta name=\\\"referrer\\\" content=\\\"no-referrer\\\">"))\nr=_checkout_csrf_referrer(r)\nassert r["Referrer-Policy"]=="same-origin"\nassert r["Cache-Control"]=="private, no-store, max-age=0"\nassert b"content=\\\"same-origin\\\"" in r.content\nassert b"no-referrer" not in r.content\nprint("PUBLIC_TRX_CSRF_HEADER_AND_META=PASS")\n'''
    code += '''from services.mpw_trx_walletless_checkout_ui import SCRIPT
assert "proofController.signal" in SCRIPT and "statusController.signal" in SCRIPT
assert "signal:controller.signal" not in SCRIPT
assert 'content="same-origin"' in open("services/mpw_trx_walletless_checkout_ui.py",encoding="utf8").read()
print("PUBLIC_TRX_INVOICE_POLLING_ISOLATION=PASS")
'''
    result=run_python(code)
    if result.returncode or 'PUBLIC_TRX_CSRF_HEADER_AND_META=PASS' not in result.stdout or 'PUBLIC_TRX_INVOICE_POLLING_ISOLATION=PASS' not in result.stdout:
        raise RuntimeError('Checkout runtime verification failed: '+result.stderr[-1200:])
    print(result.stdout.strip())

def assert_release_state():
    if pwd.getpwuid(os.getuid()).pw_name!='zomorod2': raise RuntimeError('Wrong cPanel account')
    for p in (APP,PUBLIC,BACKUP_ROOT):
        if p.is_symlink() or not p.is_dir(): raise RuntimeError('Expected production directories missing or unsafe')
    if "APP='/home/zomorod2/Saeit-staging'" not in (PUBLIC/'passenger_wsgi.py').read_text():
        raise RuntimeError('Passenger app root changed')
    settings=(APP/'config/settings.py').read_text()
    if MARK not in settings or 'MPW_WALLETLESS_TRX_PUBLIC_RELEASE_AUTHORIZED = True' not in settings or 'MPW_TRX_PUBLIC_PRODUCT_IDS = (72, 225, 879)' not in settings:
        raise RuntimeError('Public release authorization or allowlist is not installed')
    if 'MPW_WALLETLESS_TRX_PUBLIC_ENABLED = _mpw_trx_os.environ.get("MPW_WALLETLESS_TRX_PUBLIC_ENABLED", "1") == "1"' not in settings:
        raise RuntimeError('Public checkout flag is not active')

def transform_web(raw):
    if raw.count(NEW_POLICY)==1 and OLD_POLICY not in raw:return raw
    if raw.count(OLD_POLICY)!=1 or NEW_POLICY in raw or b'def _nocache(response):' not in raw or b'Cache-Control' not in raw:
        raise RuntimeError('Live no-cache policy has unexpected shape')
    return raw.replace(OLD_POLICY,NEW_POLICY,1)

def transform_pages(raw):
    helper_mark=b'def _checkout_csrf_referrer(response):'
    if helper_mark in raw:
        if raw.count(helper_mark)!=1 or raw.count(CALL)!=1: raise RuntimeError('Partially installed checkout policy helper')
        return raw
    if raw.count(META_ANCHOR)!=1 or raw.count(CSP_LINE)!=1:
        raise RuntimeError('Live checkout page source has unexpected shape')
    result=raw.replace(META_ANCHOR,HELPER+META_ANCHOR,1)
    result=result.replace(CSP_LINE,CALL+CSP_LINE,1)
    return result

def transform_invoice_ui(raw):
    marker=b'const statusController=new AbortController();'
    if marker in raw:
        if raw.count(marker)!=1 or b'const proofController=new AbortController();' not in raw or b'content="same-origin"' not in raw:
            raise RuntimeError('Partially installed invoice polling isolation')
        return raw
    allocations=b'  const controller=new AbortController();\n  const timeout=window.setTimeout(()=>controller.abort(),8000);\n  let delay=nextDelay();'
    proof_old=b'''      try{\n        await fetch(proofUrl,{method:"POST",credentials:"same-origin",cache:"no-store",\n          redirect:"error",signal:controller.signal,headers:{"Accept":"application/json","X-CSRFToken":csrf}});\n      }catch(e){/* Await next authenticated status observation; never accept browser proof. */}'''
    proof_new=b'''      const proofController=new AbortController();\n      const proofTimeout=window.setTimeout(()=>proofController.abort(),8000);\n      try{\n        await fetch(proofUrl,{method:"POST",credentials:"same-origin",cache:"no-store",\n          redirect:"error",signal:proofController.signal,headers:{"Accept":"application/json","X-CSRFToken":csrf}});\n      }catch(e){/* Await next authenticated status observation; never accept browser proof. */}\n      finally{window.clearTimeout(proofTimeout);}'''
    status_old=b'''    const r=await fetch(url,{credentials:"same-origin",cache:"no-store",redirect:"error",\n      signal:controller.signal,headers:{"Accept":"application/json"}});'''
    status_new=b'''    const statusController=new AbortController();\n    const statusTimeout=window.setTimeout(()=>statusController.abort(),8000);\n    let r;\n    try{\n      r=await fetch(url,{credentials:"same-origin",cache:"no-store",redirect:"error",\n        signal:statusController.signal,headers:{"Accept":"application/json"}});\n    }finally{window.clearTimeout(statusTimeout);}'''
    old_meta=b'<meta name="robots" content="noindex,nofollow"><meta name="referrer" content="no-referrer">'
    new_meta=b'<meta name="robots" content="noindex,nofollow"><meta name="referrer" content="same-origin">'
    for fragment in (allocations,proof_old,status_old,old_meta):
        if raw.count(fragment)!=1: raise RuntimeError('Invoice UI source shape changed')
    result=raw.replace(allocations,b'  let delay=nextDelay();',1)
    result=result.replace(proof_old,proof_new,1).replace(status_old,status_new,1).replace(old_meta,new_meta,1)
    return result

def main():
    if len(sys.argv)!=1: raise SystemExit('no arguments expected')
    assert_release_state()
    files={WEB_REL:transform_web((APP/WEB_REL).read_bytes()),PAGES_REL:transform_pages((APP/PAGES_REL).read_bytes()),INVOICE_REL:transform_invoice_ui((APP/INVOICE_REL).read_bytes())}
    old={rel:(APP/rel).read_bytes() for rel in files}
    for rel,data in files.items():compile(data.decode('utf8'),rel,'exec')
    changed={rel:data for rel,data in files.items() if data!=old[rel]}
    if not changed:
        verify_runtime();print('PUBLIC_TRX_CSRF_POLICY=ALREADY_ACTIVE');return
    backup=Path(tempfile.mkdtemp(prefix='trx-public-csrf-',dir=BACKUP_ROOT));os.chmod(backup,0o700)
    for rel in changed:
        saved=backup/Path(rel);saved.parent.mkdir(parents=True,exist_ok=True)
        saved.write_bytes(old[rel]);os.chmod(saved,0o600)
    installed=[]
    try:
        for rel,data in changed.items():
            target=APP/rel
            if target.read_bytes()!=old[rel]:raise RuntimeError('Concurrent source edit')
            put(target,data);installed.append(rel)
            if target.read_bytes()!=data:raise RuntimeError('Installed source verification failed')
        (APP/'tmp').mkdir(exist_ok=True);(APP/'tmp/restart.txt').touch()
        (PUBLIC/'tmp').mkdir(exist_ok=True);(PUBLIC/'tmp/restart.txt').touch()
        verify_runtime()
        print('PUBLIC_TRX_CSRF_POLICY=ACTIVE; CSRF_ENFORCEMENT=UNCHANGED; CROSS_ORIGIN_REFERRER=SUPPRESSED; BACKUP='+backup.name)
    except BaseException:
        for rel in reversed(installed):
            target=APP/rel
            if target.is_file() and not target.is_symlink() and target.read_bytes()==files[rel]:put(target,old[rel])
        (APP/'tmp/restart.txt').touch();(PUBLIC/'tmp/restart.txt').touch()
        print('PUBLIC_TRX_CSRF_POLICY=ROLLED_BACK');raise

if __name__=='__main__':main()
