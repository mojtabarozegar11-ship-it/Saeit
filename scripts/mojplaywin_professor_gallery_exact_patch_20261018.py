#!/usr/bin/env python3
"""Safely refresh ONLY a deployed MojPlayWin /about/mojtaba-rozegar/ static HTML file.

Adds the five official same-origin photos and removes only the requested
Persian <small> heading. Never changes .htaccess, Passenger, Django, the
independent personal website, databases, or protected commercial paths.
Rollback is an exact byte-for-byte restore, guarded against concurrent edits.
"""
import hashlib,json,os,re,stat,sys,tempfile
from pathlib import Path

ROOT=Path("/home/zomorod2/mojplaywin.com")
PAGE=ROOT/"design-preview-20261017/professor-mojtaba-roozegar-20261018.html"
HT=ROOT/".htaccess"
EXPECTED_HT="021c3b7c947f709cc39393fe6e84ba6e84c7e820122631a05c865d86e69aa464"
EXPECTED_PAGE="7ae97fae5e95163aa4dc18b36feb933f2e7f2d61ffe98beef0dc23dd98112e44"
PERSIAN_LABEL='<small lang="fa" dir="rtl">پروفسور مجتبی روزگار</small>'
SOURCE_ANCHOR='  <nav class="mpw-exec-toc" aria-label="Executive biography chapters">'
GALLERY_ANCHOR='  <section class="mpw-exec-gallery" aria-labelledby="mpw-exec-gallery-heading">'
GALLERY_END='  <nav class="mpw-exec-toc" aria-label="Executive biography chapters">'
URL_PREFIX="https://mojplaywin.com/mojtaba.roozegar/assets/personal_site/owner_gallery_20261015/"
PHOTO_PARTS=(
 "photo-01.fca592043631.jpg",
 "photo-03.6d2d8fc0fd95.jpg",
 "photo-05.ebefd3379857.jpg",
 "photo-06.b25d2c5bf84f.jpg",
 "photo-09.47d0c6608e88.jpg",
)

def sha(raw):return hashlib.sha256(raw).hexdigest()
def fail(text):raise RuntimeError(text)
def validrun(value):
    if not re.fullmatch(r"[0-9]{9,20}",value):fail("Unsafe run ID")
    return value
def source_path(run):return ROOT.parent/(".mpw-professor-gallery-"+validrun(run)+".source.html")
def backup_path(run):return ROOT.parent/(".mpw-professor-gallery-"+validrun(run)+".backup.html")
def manifest_path(run):return ROOT.parent/(".mpw-professor-gallery-"+validrun(run)+".json")
def atomic_file(path,data,mode):
    if path.is_symlink():fail("Refuse symlink target")
    fd,temporary=tempfile.mkstemp(dir=path.parent,prefix=".mpw-professor-gallery-")
    try:
        os.fchmod(fd,mode)
        with os.fdopen(fd,"wb") as stream:
            stream.write(data);stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,path)
    finally:
        if os.path.exists(temporary):os.unlink(temporary)
def extract_and_patch(original,source):
    if len(source)<20000 or len(source)>65000:fail("Editorial source size unexpected")
    if len(original)<15000 or len(original)>60000:fail("Original static page unexpected")
    if original.count(PERSIAN_LABEL)!=1:fail("Old Persian heading must occur exactly once")
    if source.count(PERSIAN_LABEL)!=0:fail("New source still contains Persian heading")
    if original.count(SOURCE_ANCHOR)!=1 or source.count(SOURCE_ANCHOR)!=1:
        fail("Table-of-contents anchor missing or ambiguous")
    if original.count(GALLERY_ANCHOR)!=0 or source.count(GALLERY_ANCHOR)!=1:
        fail("Gallery already installed or source invalid")
    start=source.index(GALLERY_ANCHOR)
    end=source.index(GALLERY_END,start)
    gallery=source[start:end]
    if gallery.count('class="mpw-exec-gallery-item"')!=5:
        fail("Must have exactly five unique additional photos")
    for suffix in PHOTO_PARTS:
        if gallery.count(URL_PREFIX+suffix)!=2:
            fail("Missing expected photo source/link or duplicate: "+suffix)
    if gallery.count('loading="lazy"')!=5 or gallery.count('alt=')<5:
        fail("Inadequate gallery accessibility/performance markup")
    css_start=source.find("\n.mpw-exec-gallery{")
    css_end=source.rfind("</style>")
    if css_start<0 or css_end<css_start:fail("No gallery styles in canonical source")
    css=source[css_start+1:css_end]
    if "mpw-exec-gallery-grid" not in css or "prefers-reduced-motion" in css:
        fail("Unexpected CSS extraction")
    current=original.replace(" "+PERSIAN_LABEL,"",1)
    current=current.replace(SOURCE_ANCHOR,gallery+SOURCE_ANCHOR,1)
    if current.count("</head>")!=1:fail("Document head invalid")
    current=current.replace("</head>",'<style id="mpw-professor-gallery-20261018">\n'+css+"\n</style>\n</head>",1)
    if PERSIAN_LABEL in current:fail("Persian heading not removed")
    if "پروفسور مجتبی روزگار" in current or "پرفسور مجتبی روزگار" in current:fail("Requested Persian professor label still visible")
    if "Professor Mojtaba Roozegar" not in current:fail("English title was lost")
    if current.count(GALLERY_ANCHOR)!=1 or current.count('class="mpw-exec-gallery-item"')!=5:
        fail("Wrong gallery count")
    for preserved in ("Universiti Putra Malaysia","Production Economics and Farm Management",
        "MOJPLAYWIN_PROFESSOR_MOJTabA_ROOZEGAR_PROFILE_20261018",
        "mpw-education","mpw-credentials", "official_profile_20261016/portrait.2935ce8cb70d.webp"):
        if preserved not in current:fail("Existing biography content lost: "+preserved)
    if current.count("<main")!=1 or current.count("</main>")!=1:fail("Page landmarks broken")
    if current.count("<h1")!=1 or current.count("</h1>")!=1:fail("Page H1 lost")
    if not 25000<len(current.encode("utf-8"))<90000:fail("Page unexpected final size")
    return current

def guard():
    if not ROOT.is_dir() or ROOT.is_symlink():fail("Docroot not verified")
    if not PAGE.is_file() or PAGE.is_symlink():fail("Profile target unsafe")
    if not HT.is_file() or HT.is_symlink():fail("Root routing unsafe")
    if sha(HT.read_bytes())!=EXPECTED_HT:fail("Root rewrite changed; no edit")
    if sha(PAGE.read_bytes())!=EXPECTED_PAGE:fail("Live profile changed; no edit")

def install(run):
    run=validrun(run);guard()
    stage=source_path(run);backup=backup_path(run);manifest=manifest_path(run)
    if not stage.is_file() or stage.is_symlink():fail("Expected source stage missing")
    if backup.exists() or backup.is_symlink() or manifest.exists():fail("Backup collision")
    before=PAGE.read_bytes()
    after=extract_and_patch(before.decode("utf-8"),stage.read_text(encoding="utf-8")).encode("utf-8")
    with open(backup,"xb") as stream:
        os.chmod(backup,0o600)
        stream.write(before);stream.flush();os.fsync(stream.fileno())
    os.chmod(backup,0o600)
    info={"run_id":run,"before":sha(before),"after":sha(after),"bytes":len(after),
          "route":"/about/mojtaba-rozegar/","photos":list(PHOTO_PARTS)}
    with open(manifest,"x",encoding="utf-8") as stream:json.dump(info,stream)
    os.chmod(manifest,0o600)
    mode=stat.S_IMODE(PAGE.stat().st_mode)
    try:
        atomic_file(PAGE,after,mode)
        if sha(PAGE.read_bytes())!=info["after"]:fail("Atomic patch verification failed")
    except BaseException:
        if PAGE.is_file() and not PAGE.is_symlink() and sha(PAGE.read_bytes())==info["after"]:
            atomic_file(PAGE,before,mode)
        raise
    print(json.dumps({"result":"PROFESSOR_FIVE_PHOTOS_ENGLISH_ONLY_PUBLISHED",
      "previous_sha256":sha(before),"new_sha256":sha(after),"bytes":len(after),
      "five_extra_photos":True,"persian_professor_label_removed":True,
      "same_static_route":True,"passenger_restarted":False,"rollback_ready":True}))

def rollback(run):
    run=validrun(run)
    backup=backup_path(run);manifest=manifest_path(run)
    if not backup.is_file() or backup.is_symlink() or not manifest.is_file() or manifest.is_symlink():
        fail("Backup is missing or unsafe")
    info=json.loads(manifest.read_text())
    old=backup.read_bytes()
    if sha(old)!=EXPECTED_PAGE or info["before"]!=EXPECTED_PAGE:fail("Invalid source backup")
    current=PAGE.read_bytes()
    if sha(current)!=info["after"]:fail("Refuse rollback over unrelated concurrent change")
    atomic_file(PAGE,old,stat.S_IMODE(PAGE.stat().st_mode))
    if sha(PAGE.read_bytes())!=EXPECTED_PAGE:fail("Rollback digest mismatch")
    print(json.dumps({"result":"PROFESSOR_GALLERY_ROLLBACK_DONE","page_sha256":EXPECTED_PAGE}))

if __name__=="__main__":
    if len(sys.argv)!=3:fail("Usage install|rollback RUN_ID")
    if sys.argv[1]=="install":install(sys.argv[2])
    elif sys.argv[1]=="rollback":rollback(sys.argv[2])
    else:fail("Unknown operation")
