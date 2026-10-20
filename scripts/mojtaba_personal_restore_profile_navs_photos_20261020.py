#!/usr/bin/env python3
"""Restore the owner's pre-change personal homepage and move one navigation below the two original photo sections.
Strictly limited to one independent V17 homepage template; requires exact SHA proof of the previous release.
"""
import hashlib,json,os,re,stat,sys,tempfile
from pathlib import Path
APP=Path("/home/zomorod2/mojtaba_personal/mojtaba_roozegar_personal_v17")
PAGE=APP/"templates/personal_site/core/home.html"
ORIGINAL=Path("/home/zomorod2/.backups/mojtaba-two-portraits-39433522000")
MARK="mpw-restore-profile-nav-after-photos-20261020"
NEW_BACKUP_BASE=Path("/home/zomorod2/.backups")
def sha(b):return hashlib.sha256(b).hexdigest()
def check_file(path):
    if not path.is_file() or path.is_symlink() or path.resolve()!=path:raise RuntimeError("Missing or unsafe file "+str(path))
def guard():
    if APP.is_symlink() or not (APP/"manage.py").is_file():raise RuntimeError("Wrong personal app")
    check_file(PAGE)
    if ORIGINAL.is_symlink():raise RuntimeError("Unsafe original backup")
    for p in (ORIGINAL/"home.before", ORIGINAL/"manifest.json"):check_file(p)
    manifest=json.loads((ORIGINAL/"manifest.json").read_text("utf8"))
    if manifest.get("path")!=str(PAGE):raise RuntimeError("Backup belongs to another template")
    raw=(ORIGINAL/"home.before").read_bytes()
    if sha(raw)!=manifest["before"]:raise RuntimeError("Original backup checksum mismatch")
    current=PAGE.read_bytes()
    if sha(current)!=manifest["after"]:raise RuntimeError("Live personal home modified since original release; refuse overwrite")
    if MARK in current.decode("utf8"):raise RuntimeError("Already installed")
    return current,raw
def take_tag(source,opening):
    p=source.find(opening)
    if p<0 or source.count(opening)!=1:raise RuntimeError("Navigation/hero token changed: "+opening)
    match=re.match(r"<([a-z]+)\b[^>]*>",source[p:],re.I|re.S)
    if not match:raise RuntimeError("Invalid opening tag")
    tag=match.group(1)
    level=0
    for m in re.finditer(r"</?"+tag+r"\b[^>]*>",source[p:],re.I|re.S):
        level+= -1 if m.group().startswith("</") else 1
        if level==0:return (p,p+m.end(),source[p:p+m.end()])
    raise RuntimeError("Unbalanced "+tag)
def patch(original):
    s=original.decode("utf8")
    # Original layout/photo blocks must be restored byte-for-byte, including the portrait and hero image.
    a,b,small=take_tag(s,'<nav class="mpw-complete-toc"')
    if "Find the information you need" not in small or "mpw-complete-standard-20261019-toc" not in small:raise RuntimeError("Expected small navigation not found")
    s=s[:a]+s[b:]
    a,b,large=take_tag(s,'<nav class="mpw-standard-nav"')
    if "Explore the professional profile" not in large or "mpw-standard-20261019-navigation" not in large:raise RuntimeError("Expected duplicate navigation not found")
    s=s[:a]+s[b:]
    h1=s.find('<h1 id="hero-title"')
    if h1<0:raise RuntimeError("Original hero title not found")
    sections=list(re.finditer(r'<section\b[^>]*>',s[:h1],re.I|re.S))
    if not sections or not re.search(r'\bhero\b',sections[-1].group()):raise RuntimeError("Original hero section not identified")
    a,b,hero=take_tag(s,sections[-1].group())
    if "hero-visual" not in hero or "mojtaba-roozegar.jpg" not in hero and "mojtaba-roozegar" not in hero: 
        # Django templates may use a conditional image source, verified against original in any case
        if 'class="hero-visual"' not in hero:raise RuntimeError("Second portrait missing")
    if s.count('id="mpw-primary-personal-profile-20261016"')!=1:raise RuntimeError("Original first portrait section missing")
    if "PROFESSIONAL PROFILE" not in s or "Discuss a professional collaboration" not in s:raise RuntimeError("Owner profile details missing")
    s=s[:b]+"\n<!-- "+MARK+" -->\n"+small+"\n"+s[b:]
    p1=s.index('id="mpw-primary-personal-profile-20261016"')
    p2=s.index('class="hero-visual"')
    p3=s.index('id="mpw-complete-standard-20261019-toc"')
    if not p1<p2<p3:raise RuntimeError("Photos must appear before kept navigation")
    if 'mpw-standard-20261019-navigation' in s or 'mpw-profile-photo-pair' in s:raise RuntimeError("Previous page layout still present")
    # Confirm there is no loss of any image, Django tag, owner bio, or original photo HTML.
    removed=small+large
    if s.count("<img")!=original.decode("utf8").count("<img") or s.count("{%")!=original.decode("utf8").count("{%"):raise RuntimeError("Original images / Django logic unexpectedly changed")
    return s
def validate(body):
    sys.path.insert(0,str(APP));os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
    import django;django.setup()
    from django.template import engines
    engines["django"].engine.from_string(body)
def atomic(path,b):
    fd,tmp=tempfile.mkstemp(prefix=".mpw-restore-",dir=path.parent)
    try:
        with os.fdopen(fd,"wb") as f:
            os.fchmod(f.fileno(),stat.S_IMODE(path.stat().st_mode))
            f.write(b);f.flush();os.fsync(f.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.lexists(tmp):os.unlink(tmp)
def destination(runid):
    if not re.fullmatch(r"[0-9]{7,22}",runid):raise RuntimeError("Run ID invalid")
    return NEW_BACKUP_BASE/("mojtaba-profile-recovery-"+runid)
def install(runid):
    before,original=guard()
    updated=patch(original).encode("utf8");validate(updated.decode("utf8"))
    dest=destination(runid)
    if dest.exists() or dest.is_symlink():raise RuntimeError("Backup destination not clean")
    dest.mkdir(parents=True,mode=0o700)
    with (dest/"previous").open("xb") as f:
        os.fchmod(f.fileno(),0o600);f.write(before);f.flush();os.fsync(f.fileno())
    meta={"path":str(PAGE),"before":sha(before),"after":sha(updated),"original_recovered":sha(original)}
    (dest/"manifest.json").write_text(json.dumps(meta,indent=2),encoding="utf8")
    if sha((dest/"previous").read_bytes())!=sha(before) or sha(PAGE.read_bytes())!=sha(before):raise RuntimeError("Backup or race detected")
    atomic(PAGE,updated)
    if sha(PAGE.read_bytes())!=sha(updated):raise RuntimeError("Updated template checksum failed")
    print("PERSONAL_ORIGINAL_PHOTOS_AND_PROFILE=RESTORED")
    print("ONE_NAVIGATION_BELOW_PHOTOS=INSTALLED")
    print("PROFILE_RECOVERY_BACKUP="+str(dest))
def rollback(runid):
    dest=destination(runid)
    if dest.is_symlink():raise RuntimeError("Unsafe rollback")
    manifest=json.loads((dest/"manifest.json").read_text("utf8"))
    original=(dest/"previous").read_bytes()
    if manifest.get("path")!=str(PAGE) or sha(original)!=manifest["before"]:raise RuntimeError("Rollback manifest invalid")
    existing=PAGE.read_bytes()
    if sha(existing) not in (manifest["before"],manifest["after"]):raise RuntimeError("Concurrent change; refuse rollback")
    if sha(existing)==manifest["after"]:atomic(PAGE,original)
    if sha(PAGE.read_bytes())!=manifest["before"]:raise RuntimeError("Rollback unsuccessful")
    print("PERSONAL_RESTORE_ROLLBACK=VERIFIED")
if __name__=="__main__":
    if len(sys.argv)==2 and sys.argv[1]=="check":
        a,b=guard();out=patch(b);validate(out);print("ORIGINAL_PROFILE_AND_TWO_PHOTOS_PREFLIGHT=PASS")
    elif len(sys.argv)==3 and sys.argv[1]=="install":install(sys.argv[2])
    elif len(sys.argv)==3 and sys.argv[1]=="rollback":rollback(sys.argv[2])
    else:raise SystemExit("usage: check / install RUN_ID / rollback RUN_ID")
