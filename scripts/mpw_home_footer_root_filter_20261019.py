#!/usr/bin/env python3
"""MojPlayWin / root-only HTML-response footer enhancer.

Modifies only the domain document-root .htaccess (append a path == '/'
HTML output filter) plus one new small static JavaScript asset.
No WSGI, Django, other routes, nested sites, apps, databases or payments.
Includes atomic backed-up rollback on any verification failure.
"""
from pathlib import Path
import hashlib,json,os,pwd,re,stat,sys,tempfile

HOME=Path("/home/zomorod2")
ROOT=HOME/"mojplaywin.com"
HT=ROOT/".htaccess"
ASSET=ROOT/"design-preview-20261017/static/site/mpw-home-legal-footer-20261019.js"
PUBLIC_ASSET="/design-preview-20261017/static/site/mpw-home-legal-footer-20261019.js"
START="# BEGIN MPW_HOME_LEGAL_FOOTER_20261019"
END="# END MPW_HOME_LEGAL_FOOTER_20261019"
LINE="☆ All Rights Reserved. ☆ 2022. ☆ Mojtaba roozegar ☆"
JS=r"""(function(){
'use strict';
if(window.location.pathname!=='/' || !/^(?:www\.)?mojplaywin\.com$/i.test(window.location.hostname))return;
function update(){
  var matched=Array.prototype.filter.call(document.querySelectorAll('footer'),function(f){
    return f.classList.contains('mw-site-footer') || f.classList.contains('mpw-footer');
  });
  if(matched.length!==1)return;
  var footer=matched[0];
  var bar=footer.querySelector('.mpx-bottom-bar');
  if(!bar)return;
  if(bar.querySelector('.mpw-legal-one-line'))return;
  if(!/Mojtaba Roozegar/.test(bar.textContent||'') || !/All rights reserved/i.test(bar.textContent||''))return;
  var span=document.createElement('span');
  span.className='mpw-legal-one-line';
  span.setAttribute('data-mpw-final-founder','true');
  span.setAttribute('data-mpw-founder-source','Mojtaba Roozegar');
  span.setAttribute('aria-label','All Rights Reserved. 2022. Mojtaba roozegar');
  span.textContent='☆ All Rights Reserved. ☆ 2022. ☆ Mojtaba roozegar ☆';
  span.style.cssText='display:block;box-sizing:border-box;width:100%;max-width:100%;white-space:nowrap;overflow-x:auto;text-align:center;font-size:clamp(10px,2.5vw,14px);line-height:1.5;letter-spacing:0;font-weight:750;color:#f3d184;padding:10px 4px';
  bar.replaceChildren(span);
  bar.style.cssText='box-sizing:border-box;display:block;flex:1 1 100%;grid-column:1/-1;width:100%;max-width:100%;text-align:center';
  if(!document.getElementById('mpw-home-footer-singleline-style')){
    var style=document.createElement('style');
    style.id='mpw-home-footer-singleline-style';
    style.textContent='body.mojplaywin-home footer.mw-site-footer:has(.mpw-legal-one-line)::after{content:none!important;display:none!important}body.mojplaywin-home footer.mw-site-footer .mpw-legal-one-line{white-space:nowrap!important}';
    footer.appendChild(style);
  }
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',update,{once:true});
else update();
})();"""
BLOCK=(
  "\n"+START+"\n"+
  "# Only public main-domain homepage / output receives this script.\n"
  "# Other main pages, child sites, POST, handlers, routes remain untouched.\n"
  "<IfModule mod_substitute.c>\n<IfModule mod_filter.c>\n"
  '<If "%{REQUEST_URI} =~ m#^/$#">\n'
  "  AddOutputFilterByType SUBSTITUTE text/html\n"
  '  Substitute "s|</body>|<script src=\''+PUBLIC_ASSET+'\' defer></script></body>|ni"\n'
  "</If>\n</IfModule>\n</IfModule>\n"+END+"\n"
)

def sha(raw):return hashlib.sha256(raw).hexdigest()
def fail(t):raise RuntimeError(t)
def backupdir(run):
    if not re.fullmatch(r"[0-9]{9,20}",run):fail("Invalid run ID")
    return HOME/(".mpw-home-legal-footer-"+run)
def ensure():
    if pwd.getpwuid(os.getuid()).pw_name!="zomorod2":fail("Wrong account")
    if not ROOT.is_dir() or ROOT.is_symlink() or ROOT.resolve()!=ROOT:fail("Wrong website root")
    if not HT.is_file() or HT.is_symlink() or ASSET.parent.is_symlink() or not ASSET.parent.is_dir():
        fail("Untrusted document root target")
    current=HT.read_text("utf-8",errors="replace")
    if "PassengerAppRoot /home/zomorod2/mojplaywin.com" not in current:
        fail("Main-domain Apache root changed")
    if START in current or END in current:fail("Root-only filter already installed")
    if ASSET.exists() or ASSET.is_symlink():fail("Target JS already exists")
    if current.count("# MPW_MAIN_19_EXACT_DYNAMIC_SHELL_20261019_BEGIN")!=1:
        fail("19-route main-only PHP guard missing")
def atom(path,bytes_,mode,creation=False):
    if path.is_symlink():fail("Symlink target")
    if not creation and not path.is_file():fail("File absent")
    fd,tmp=tempfile.mkstemp(prefix=".mpw-home-footer-",dir=path.parent)
    try:
        os.fchmod(fd,mode)
        with os.fdopen(fd,"wb") as f:
            f.write(bytes_);f.flush();os.fsync(f.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.lexists(tmp):os.unlink(tmp)
def install(run):
    ensure()
    backup=backupdir(run)
    if backup.exists():fail("Backup already exists")
    old=HT.read_bytes()
    new=old+BLOCK.encode("utf-8")
    asset=JS.encode("utf-8")
    if asset.count(LINE.encode("utf-8"))!=1:fail("JS must contain exactly one rights string")
    if "m#^/$#" not in BLOCK or "AddOutputFilterByType SUBSTITUTE text/html" not in BLOCK:
        fail("Root-only filter must not change routing")
    backup.mkdir(mode=0o700)
    original=backup/"original.htaccess"
    with original.open("xb") as f:
        os.fchmod(f.fileno(),0o600);f.write(old);f.flush();os.fsync(f.fileno())
    meta={"run":run,"old":sha(old),"new":sha(new),"asset":sha(asset)}
    with (backup/"manifest.json").open("x") as f:
        os.fchmod(f.fileno(),0o600);json.dump(meta,f);f.flush();os.fsync(f.fileno())
    if HT.read_bytes()!=old:fail("Concurrent Apache config update")
    atom(ASSET,asset,0o644,creation=True)
    try:
        atom(HT,new,stat.S_IMODE(HT.stat().st_mode))
        if sha(HT.read_bytes())!=meta["new"] or sha(ASSET.read_bytes())!=meta["asset"]:
            fail("Post-install checksum mismatch")
    except BaseException:
        if sha(HT.read_bytes())==meta["new"]:atom(HT,old,stat.S_IMODE(HT.stat().st_mode))
        if ASSET.is_file() and sha(ASSET.read_bytes())==meta["asset"]:ASSET.unlink()
        raise
    (backup/"INSTALLED").write_text("true")
    print("MPW_HOME_ONLY_FOOTER_FILTER_INSTALLED=true",flush=True)
def rollback(run):
    backup=backupdir(run)
    if not backup.is_dir() or backup.is_symlink():fail("Backup missing")
    info=json.loads((backup/"manifest.json").read_text("utf-8"))
    old=(backup/"original.htaccess").read_bytes()
    if info["run"]!=run or sha(old)!=info["old"]:fail("Original Apache file corrupted")
    if sha(HT.read_bytes())!=info["new"] or not ASSET.is_file() or ASSET.is_symlink() or sha(ASSET.read_bytes())!=info["asset"]:
        fail("Refuse rollback over concurrent edits")
    atom(HT,old,stat.S_IMODE(HT.stat().st_mode))
    ASSET.unlink()
    if sha(HT.read_bytes())!=info["old"]:fail("Apache rollback verification failed")
    print("MPW_HOME_ONLY_FOOTER_FILTER_ROLLBACK=VERIFIED",flush=True)
def selftest():
    assert LINE in JS and JS.count(LINE)==1
    assert 'window.location.pathname!==\'/\'' in JS
    assert 'matched.length!==1' in JS
    assert "bar.replaceChildren(span)" in JS
    assert BLOCK.count("<If ")==1
    assert BLOCK.count("REQUEST_URI")==1
    assert "m#^/$#" in BLOCK
    assert "^(store|games" not in BLOCK
    assert ".htaccess" in str(HT) and "farnaz" not in BLOCK
    print("MPW_HOME_FOOTER_FILTER_SELFTEST=PASS")
if __name__=="__main__":
    if len(sys.argv)==2 and sys.argv[1]=="selftest":selftest()
    elif len(sys.argv)==3 and sys.argv[1]=="install":install(sys.argv[2])
    elif len(sys.argv)==3 and sys.argv[1]=="rollback":rollback(sys.argv[2])
    else:fail("selftest|install RUN|rollback RUN")
