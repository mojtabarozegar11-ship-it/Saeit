#!/usr/bin/env python3
"""One-field footer correction for Zomorod homepage. Atomic, immutable baseline, rollback.
Never replaces templates, images, CSS, JS, .htaccess or data.
"""
from __future__ import annotations
import fcntl, hashlib, json, os, pwd, re, stat, sys, tempfile
from pathlib import Path
from contextlib import contextmanager

SITE=Path("/home/zomorod2/public_html")
HOME=SITE/"index.html"
STAGE=Path(__file__).resolve().parent
BASE=Path("/home/zomorod2/.backups")
BACKUP=BASE/"zomorod-footer-rights-aban1398-20261113"
LOCK=BASE/".zomorod-homepage-deploy.lock"
ARCHIVE=SITE/"site-heritage/home-before-nexus-20261112/index.html"
OLD_TEXT="© ۲۰۲۶ شرکت کشت و صنعت زمرد ملل · حقوق محفوظ است.".encode("utf-8")
NEW_TEXT="© شرکت کشت و صنعت زمرد ملل | آبان ۱۳۹۸ | کلیه حقوق مادی و معنوی محفوظ است.".encode("utf-8")
PROTECTED=(
 ".htaccess","sitemap.xml","agriculture/index.html","industry/index.html",
 "research/index.html","services/index.html","contact/index.html",
 "company/index.html","store/index.php","games/index.html",
 "apps/index.html","auctions/index.html",
 "assets/zm-reference-v3.css","assets/zm-reference-v3.js",
 "static/site/zomorod-v7/company-logo.webp"
)

def h(b:bytes)->str:return hashlib.sha256(b).hexdigest()
def safe(p:Path)->bytes:
 if p.is_symlink() or not p.is_file():raise RuntimeError("Source missing or symlink: "+str(p))
 return p.read_bytes()
def release_id(v:str)->Path:
 if not re.fullmatch(r"rights-[0-9]{8,25}",v):raise RuntimeError("Unsafe release id")
 return BACKUP/v
def account():
 if pwd.getpwuid(os.geteuid()).pw_name!="zomorod2":raise RuntimeError("Unexpected account")
 for p in (SITE,STAGE,BASE):
  if not p.is_dir() or p.is_symlink():raise RuntimeError("Unsafe directory: "+str(p))
 if BACKUP.is_symlink() or LOCK.is_symlink():raise RuntimeError("Unsafe backup path")
def files():
 original=safe(STAGE/"old.html")
 revised=safe(STAGE/"new.html")
 if original.count(OLD_TEXT)!=1 or original.count(NEW_TEXT)!=0:
  raise RuntimeError("Old source not exact canonical footer")
 if revised.count(NEW_TEXT)!=1 or revised.count(OLD_TEXT)!=0:
  raise RuntimeError("New source missing required rights")
 if original.replace(OLD_TEXT,NEW_TEXT,1)!=revised:
  raise RuntimeError("More than one HTML span altered; fail closed")
 if original.count(b"<footer ")!=1 or revised.count(b"<footer ")!=1:
  raise RuntimeError("Not the known homepage")
 return original,revised
def protected():
 x={}
 for name in PROTECTED:
  p=SITE/name
  if p.exists():x[name]=h(safe(p))
 if len(x)<10:raise RuntimeError("Insufficient protected site files")
 return x
def inspection():
 account()
 old,new=files()
 if h(safe(HOME))!=h(old):raise RuntimeError("Live HTML differs from pinned GitHub revision")
 return {"old":h(old),"new":h(new),"protected":protected(),"archive":h(safe(ARCHIVE)),
         "mode":stat.S_IMODE(HOME.stat().st_mode)}
def atomic(p:Path,data:bytes,mode:int):
 temp=None
 try:
  with tempfile.NamedTemporaryFile(prefix=".zm-rights-",dir=p.parent,delete=False) as handle:
   temp=Path(handle.name);handle.write(data);handle.flush();os.fsync(handle.fileno())
  os.chmod(temp,mode);os.replace(temp,p)
 finally:
  if temp and temp.exists():temp.unlink()
@contextmanager
def lock():
 with open(LOCK,"a+b") as file:
  fcntl.flock(file.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
  try:yield
  finally:fcntl.flock(file.fileno(),fcntl.LOCK_UN)
def stored(run):
 folder=release_id(run)
 manifest=json.loads(safe(folder/"manifest.json").decode("utf-8"))
 old=safe(folder/"old.html")
 if h(old)!=manifest["old"]:raise RuntimeError("Private backup corrupted")
 return folder,manifest,old
def verify(run):
 account()
 folder,m,old=stored(run)
 if h(safe(HOME))!=m["new"]:raise RuntimeError("Live footer revision mismatch")
 if protected()!=m["protected"]:raise RuntimeError("Protected site altered")
 if h(safe(ARCHIVE))!=m["archive"]:raise RuntimeError("Historic homepage altered")
 if safe(HOME).count(NEW_TEXT)!=1:raise RuntimeError("Required text absent")
 print("ZM_FOOTER_ABAN1398_AND_EXACT_RIGHTS=VERIFIED")
 print("ZM_FOOTER_PROTECTED_INNER_FILES=UNCHANGED")
def apply(run):
 with lock():
  m=inspection()
  folder=release_id(run)
  if folder.exists() or folder.is_symlink():raise RuntimeError("Backup namespace already used")
  folder.mkdir(parents=True,mode=0o700)
  old,new=files()
  atomic(folder/"old.html",old,0o600)
  if h(safe(folder/"old.html"))!=m["old"]:raise RuntimeError("Private backup failed")
  (folder/"manifest.json").write_text(json.dumps(m,sort_keys=True),encoding="utf-8")
  if h(safe(HOME))!=m["old"]:raise RuntimeError("Concurrent live edit — not overwriting")
  try:
   atomic(HOME,new,m["mode"])
   verify(run)
  except BaseException:
   if h(safe(HOME))==m["new"]:atomic(HOME,old,m["mode"])
   raise
  print("ZM_FOOTER_ONE_FIELD_UPDATED=YES")
def rollback(run):
 with lock():
  account()
  _,m,old=stored(run)
  now=h(safe(HOME))
  if now==m["new"]:atomic(HOME,old,m["mode"])
  elif now!=m["old"]:raise RuntimeError("Concurrent change — never overwrite")
  if h(safe(HOME))!=m["old"] or protected()!=m["protected"]:
   raise RuntimeError("Rollback check failed")
  if h(safe(ARCHIVE))!=m["archive"]:raise RuntimeError("Archive changed")
  print("ZM_FOOTER_ORIGINAL_RESTORED=YES")
def selftest():
 old=b"<footer> "+OLD_TEXT+b" </footer>"
 new=old.replace(OLD_TEXT,NEW_TEXT)
 assert old.replace(OLD_TEXT,NEW_TEXT,1)==new
 assert new.replace(NEW_TEXT,OLD_TEXT,1)==old
 print("ZM_FOOTER_RIGHTS_EXACT_REPLACEMENT=PASS")
if __name__=="__main__":
 if len(sys.argv)==2 and sys.argv[1]=="selftest":selftest()
 elif len(sys.argv)==2 and sys.argv[1]=="inspect":print(json.dumps(inspection(),sort_keys=True))
 elif len(sys.argv)==3 and sys.argv[1] in ("apply","verify","rollback"):
  {"apply":apply,"verify":verify,"rollback":rollback}[sys.argv[1]](sys.argv[2])
 else:raise SystemExit("Usage: selftest | inspect | apply|verify|rollback RUN")
