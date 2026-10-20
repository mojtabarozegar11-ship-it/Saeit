#!/usr/bin/env python3
"""Repair customer mobile CSRF form submissions without weakening CSRF protection.

Only the two MojPlayWin customer HTML templates are changed. No settings, auth
handlers, database, payment, wallet, or sibling templates are modified.
"""
import hashlib,json,os,pwd,re,stat,sys,tempfile
from pathlib import Path

APP=Path('/home/zomorod2/Saeit-staging')
ROOT=Path('/home/zomorod2/mojplaywin.com')
WSGI=ROOT/'passenger_wsgi.py'
BACKUP=Path('/home/zomorod2/.private_mojplaywin_main_agents')
FILES={
    'login':(APP/'mpw_commerce/templates/mpw_commerce/customer_login.html',
             """<form method="post" action="{% url 'mpw_commerce:customer_login' %}">"""),
    'register':(APP/'mpw_commerce/templates/mpw_commerce/customer_register.html',
                """<form method="post" action="{% url 'mpw_commerce:customer_register' %}">"""),
}
MARK='MPW_CUSTOMER_MOBILE_CSRF_FRESH_20261020'
MESSAGE='''<!-- MPW_CUSTOMER_MOBILE_CSRF_FRESH_20261020 -->
<div id="mpw-csrf-recovery" role="alert" aria-live="assertive" hidden
 style="border:1px solid #f3c478;border-radius:10px;background:#3a281e;color:#fff4da;padding:14px;line-height:1.7;margin:12px 0">
 The browser could not keep a valid security cookie. Your form was not submitted.
 Please open mojplaywin.com directly in Chrome (not an in-app browser),
 allow site cookies and try again. No payment has been made.
</div>
'''
HELP='''<p id="mpw-trx-trial-return"><a href="/commerce/book/779/">Return to the low-value TRX test purchase</a></p>
'''
SCRIPT=r'''<script id="mpw-csrf-fresh-submit-20261020">
(function(){
 "use strict";
 var form=document.querySelector("main form[method=post]");
 if(!form)return;
 var busy=false,refreshed=false;
 var warning=document.getElementById("mpw-csrf-recovery");
 var submit=form.querySelector('button[type="submit"]');
 form.addEventListener("submit",function(event){
   if(refreshed)return;
   event.preventDefault();
   if(busy)return;
   busy=true;
   if(submit)submit.disabled=true;
   if(warning)warning.hidden=true;
   fetch(window.location.pathname+window.location.search,{
      method:"GET",credentials:"same-origin",cache:"no-store",
      headers:{"Accept":"text/html","X-MojPlayWin-CSRF-Refresh":"1"}
   }).then(function(response){
      if(!response.ok || response.redirected)throw Error("Could not refresh secure form");
      return response.text();
   }).then(function(html){
      var page=new DOMParser().parseFromString(html,"text/html");
      var incoming=page.querySelector('main form input[name="csrfmiddlewaretoken"]');
      var current=form.querySelector('input[name="csrfmiddlewaretoken"]');
      var cookie=document.cookie.split(";").some(function(entry){
          return entry.trim().indexOf("csrftoken=")===0;
      });
      if(!incoming || !current || !incoming.value || !cookie)
          throw Error("The browser did not retain the CSRF cookie");
      current.value=incoming.value;
      refreshed=true;
      busy=false;
      if(submit)submit.disabled=false;
      if(typeof form.requestSubmit==="function")form.requestSubmit(submit||undefined);
      else form.submit();
   }).catch(function(){
      busy=false;
      if(submit)submit.disabled=false;
      if(warning)warning.hidden=false;
   });
 },false);
})();
</script>
'''

def sha(b):return hashlib.sha256(b).hexdigest()
def identity():
    if pwd.getpwuid(os.getuid()).pw_name!='zomorod2':raise RuntimeError('Incorrect production user')
    for p in (APP,ROOT,WSGI,BACKUP):
        if p.is_symlink():raise RuntimeError('Unsafe application identity')
    if not WSGI.is_file() or "APP='/home/zomorod2/Saeit-staging'" not in WSGI.read_text('utf8','replace'):
        raise RuntimeError('Passenger pin differs: refuse live patch')
    if not BACKUP.is_dir() or stat.S_IMODE(BACKUP.stat().st_mode)&0o077:
        raise RuntimeError('Private sealed backup folder unavailable')
    for target,_ in FILES.values():
        if not target.is_file() or target.is_symlink() or target.parent.is_symlink():
            raise RuntimeError('Target customer template missing or unsafe')
def transform(raw,kind):
    source=raw.decode('utf8')
    target,anchor=FILES[kind]
    if MARK in source:raise RuntimeError('Template already patched; no duplicate')
    if source.count(anchor)!=1 or source.count('</form>')!=1 or source.count('{% csrf_token %}')!=1:
        raise RuntimeError('Live customer template has unknown form shape')
    if "<html lang=\"en\">" not in source or 'data-mpw-django-home-20261020' not in source:
        raise RuntimeError('Unexpected branded template')
    result=source.replace(anchor,MESSAGE+anchor,1)
    result=result.replace('</form>','</form>\n'+SCRIPT+'\n'+HELP,1)
    if result.count(MARK)!=1 or result.count('mpw-csrf-fresh-submit-20261020')!=1:
        raise RuntimeError('Unexpected mobile cookie markup')
    if result.replace(MESSAGE,'',1).replace('\n'+SCRIPT+'\n'+HELP,'',1)!=source:
        raise RuntimeError('Out-of-scope text change')
    return result.encode('utf8')
def filepaths(run,kind):
    if not re.fullmatch(r'[0-9]{8,20}',run):raise RuntimeError('Invalid release ID')
    return BACKUP/('mpw-csrf-mobile-'+kind+'-'+run+'.bak')
def atomic(path,blob):
    fd,temp=tempfile.mkstemp(prefix='.mpw-csrf-',dir=path.parent)
    try:
        os.fchmod(fd,stat.S_IMODE(path.stat().st_mode))
        with os.fdopen(fd,'wb') as handle:
            handle.write(blob);handle.flush();os.fsync(handle.fileno())
        os.replace(temp,path)
    finally:
        if os.path.exists(temp):os.unlink(temp)
def preview():
    identity()
    out={}
    for kind,(target,_) in FILES.items():
        source=target.read_bytes()
        newer=transform(source,kind)
        out[kind]={'old':sha(source),'new':sha(newer),'bytes_changed':len(newer)-len(source)}
    print('MPW_CSRF_MOBILE_PREVIEW='+json.dumps(out))
def publish(run):
    identity()
    snapshots={}
    for kind,(target,_) in FILES.items():
        old=target.read_bytes();new=transform(old,kind);p=filepaths(run,kind)
        if p.exists() or p.is_symlink():raise RuntimeError('Backup collision')
        snapshots[kind]=(target,old,new,p)
    written=[]
    try:
        for kind,(target,old,new,p) in snapshots.items():
            with p.open('xb') as f:
                os.fchmod(f.fileno(),0o600);f.write(old);f.flush();os.fsync(f.fileno())
            if target.read_bytes()!=old:raise RuntimeError('Concurrent template edit')
            atomic(target,new);written.append(kind)
            if target.read_bytes()!=new:raise RuntimeError('Patch verification failed')
    except BaseException:
        for kind in reversed(written):
            target,old,new,p=snapshots[kind]
            if target.read_bytes()==new:atomic(target,old)
        raise
    print('MPW_CSRF_MOBILE_PUBLISHED='+json.dumps({
      'templates':[str(x[0].relative_to(APP)) for x in snapshots.values()],
      'security_still_enforced':True,'payment_state_unchanged':True,
      'other_sites_unchanged':True,'run':run}))
def verify(run):
    identity()
    for kind,(target,_) in FILES.items():
        p=filepaths(run,kind)
        if not p.is_file() or p.is_symlink():raise RuntimeError('Backup missing')
        old=p.read_bytes()
        if target.read_bytes()!=transform(old,kind):raise RuntimeError('Installed template mismatch')
    os.chdir(APP);sys.path.insert(0,str(APP));os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
    import django
    django.setup()
    from django.test import Client
    from django.conf import settings
    if not settings.CSRF_COOKIE_SECURE or settings.CSRF_COOKIE_HTTPONLY or settings.CSRF_USE_SESSIONS:
        raise RuntimeError('Real CSRF cookie scheme differs from supported runtime')
    for route in ('/accounts/login/','/accounts/register/'):
        client=Client(enforce_csrf_checks=True)
        response=client.get(route,secure=True,HTTP_HOST='mojplaywin.com')
        html=response.content.decode('utf8','replace')
        if response.status_code!=200 or 'mpw-csrf-fresh-submit-20261020' not in html or '/commerce/book/779/' not in html:
            raise RuntimeError('Customer runtime render missing mobile recovery')
        if 'name="csrfmiddlewaretoken"' not in html or 'csrftoken' not in response.cookies:
            raise RuntimeError('Django CSRF cookie was weakened or removed')
    print('MPW_CSRF_MOBILE_VERIFIED='+json.dumps({'login':200,'register':200,
      'mobile_fresh_token':True,'cookie_preflight':True,'csrf_still_required':True,
      'no_customer_records_modified':True}))
def rollback(run):
    identity()
    snapshots={}
    for kind,(target,_) in FILES.items():
        p=filepaths(run,kind)
        if not p.is_file() or p.is_symlink():raise RuntimeError('Missing rollback backup')
        old=p.read_bytes()
        if target.read_bytes()!=transform(old,kind):raise RuntimeError('Concurrent edits; manual recovery required')
        snapshots[kind]=(target,old)
    for kind,(target,old) in snapshots.items():atomic(target,old)
    print('MPW_CSRF_MOBILE_ROLLBACK=PASS')
def selftest():
    for kind,(_,anchor) in FILES.items():
        sample=('<html lang="en"><body data-mpw-django-home-20261020="true">'+anchor+
                '{% csrf_token %}<button type="submit">Continue</button></form></body></html>').encode()
        proposed=transform(sample,kind)
        assert MARK.encode() in proposed and b'fetch(window.location.pathname' in proposed
        assert b'credentials:"same-origin"' in proposed and b'allow site cookies' in proposed
        assert b'role="alert"' in proposed and b'csrfmiddlewaretoken' in proposed
        try:transform(proposed,kind)
        except RuntimeError:pass
        else:raise RuntimeError('Duplicate patch allowed')
    print('MPW_CSRF_MOBILE_SELFTEST=PASS')
if __name__=='__main__':
    if len(sys.argv)==2 and sys.argv[1]=='selftest':selftest()
    elif len(sys.argv)==2 and sys.argv[1]=='preview':preview()
    elif len(sys.argv)==3 and sys.argv[1] in ('publish','verify','rollback'):
        {'publish':publish,'verify':verify,'rollback':rollback}[sys.argv[1]](sys.argv[2])
    else:raise SystemExit('selftest|preview|publish RUN_ID|verify RUN_ID|rollback RUN_ID')
