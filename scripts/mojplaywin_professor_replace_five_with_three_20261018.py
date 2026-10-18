#!/usr/bin/env python3
"""Replace only MojPlayWin professor static-page's unwanted five-photo gallery.

Reads the already-published static /about/mojtaba-rozegar/ page and the vetted
GitHub CV source (staged privately). Five earlier photo cards are replaced by
the two sport and one white-shirt crops already chosen on the personal site.
Preserves hero portrait, academic text, canonical URL, payments and sibling sites.
"""
from pathlib import Path
import hashlib,json,os,re,stat,sys,tempfile

ROOT=Path("/home/zomorod2/mojplaywin.com")
PAGE=ROOT/"design-preview-20261017/professor-mojtaba-roozegar-20261018.html"
HT=ROOT/".htaccess"
EXPECTED_HT="021c3b7c947f709cc39393fe6e84ba6e84c7e820122631a05c865d86e69aa464"
EXPECTED_PAGE="69aec708c67c5d3af34a72b5e63b8883e826ee77510c7b71ec70aec2e1b47646"
OLD_START='  <section class="mpw-exec-gallery" aria-labelledby="mpw-exec-gallery-heading">'
NEW_START='  <section class="mpw-sport-white-selection" id="mpw-sport-white-selection-20261018"'
NEXT='  <nav class="mpw-exec-toc" aria-label="Executive biography chapters">'
OLD_STYLE_ID="mpw-professor-gallery-20261018"
NEW_STYLE_ID="mpw-sport-white-selection-style-20261018"
SOURCE="https://mojplaywin.com/mojtaba.roozegar/assets/personal_site/owner_gallery_20261015_b/photo-09.7a4e0222fb28.png"
OLD_PHOTOS=(
  "photo-01.fca592043631.jpg","photo-03.6d2d8fc0fd95.jpg",
  "photo-05.ebefd3379857.jpg","photo-06.b25d2c5bf84f.jpg",
  "photo-09.47d0c6608e88.jpg")
SAVED_CREDENTIALS=("Universiti Putra Malaysia","Production Economics and Farm Management",
 "MOJPLAYWIN_PROFESSOR_MOJTabA_ROOZEGAR_PROFILE_20261018",
 "Professor Mojtaba Roozegar","official_profile_20261016/portrait.2935ce8cb70d.webp")
def fail(x):raise RuntimeError(x)
def sha(x):return hashlib.sha256(x).hexdigest()
def run_id(x):
    if not re.fullmatch(r"[0-9]{9,20}",x):fail("Invalid run ID")
    return x
def stage(run):return ROOT.parent/(".mpw-professor-selected-20261018-"+run_id(run)+".source.html")
def backup(run):return ROOT.parent/(".mpw-professor-selected-20261018-"+run_id(run)+".backup.html")
def manifest(run):return ROOT.parent/(".mpw-professor-selected-20261018-"+run_id(run)+".manifest.json")
def atomic(path,raw,mode):
    if path.is_symlink():fail("Unexpected symlink")
    fd,tmp=tempfile.mkstemp(prefix=".mpw-professor-selection-",dir=path.parent)
    try:
      os.fchmod(fd,mode)
      with os.fdopen(fd,"wb") as f:f.write(raw);f.flush();os.fsync(f.fileno())
      os.replace(tmp,path)
    finally:
      if os.path.exists(tmp):os.unlink(tmp)

def validate_page(old):
    if len(old)<26000 or len(old)>50000:fail("Live static professor page bytes outside expected limits")
    if old.count(OLD_START)!=1 or old.count(NEXT)!=1:
        fail("Expected old gallery location not found")
    if NEW_START in old:fail("New gallery already present")
    if old.count('class="mpw-exec-gallery-item"')!=5:
        fail("Expected exactly 5 old cards")
    if old.count('<style id="'+OLD_STYLE_ID+'">')!=1:fail("Expected precisely one previous gallery stylesheet")
    for filename in OLD_PHOTOS:
        if old.count(filename)!=2:fail("Old gallery content differs: "+filename)
    for marker in SAVED_CREDENTIALS:
        if marker not in old:fail("Important published profile content absent")
    if old.count("<main")!=1 or old.count("</main>")!=1:fail("Invalid main landmark")
    if old.count("<h1")!=1:fail("Invalid H1 landmark")

def make_new(old,source):
    validate_page(old)
    if source.count(NEW_START)!=1 or OLD_START in source:
        fail("Vetted new source is unexpected")
    start=source.index(NEW_START)
    end=source.index(NEXT,start)
    selected=source[start:end]
    if selected.count('class="mpw-sport-white-card ' )!=3:fail("Source new gallery must have 3 photo cards")
    if selected.count(SOURCE)!=3:fail("Wrong image source for the chosen original four-view image")
    if not all(x in selected for x in (
      'Casual sport portrait','Outdoor sport-jacket portrait','White-shirt portrait',
      '--mpw-crop-offset:0%','--mpw-crop-offset:-75%','--mpw-crop-offset:-50%',
      'loading="lazy"','alt=')):fail("Selected perspectives incomplete")
    css_start=source.find("\n.mpw-sport-white-selection{")
    css_end=source.find("\n</style>",css_start)
    if css_start<0 or css_end<0:fail("New gallery style missing")
    css=source[css_start+1:css_end]
    if "mpw-sport-white-grid" not in css:fail("Gallery CSS incomplete")
    i=old.index(OLD_START)
    j=old.index(NEXT,i)
    result=old[:i]+selected+old[j:]
    old_css_pattern=r'<style id="'+OLD_STYLE_ID+r'">.*?</style>\s*'
    result,count=re.subn(old_css_pattern,"",result,count=1,flags=re.S)
    if count!=1:fail("Old gallery CSS not removable as a single block")
    if result.count("</head>")!=1:fail("Head changed unexpectedly")
    result=result.replace("</head>",'<style id="'+NEW_STYLE_ID+'">\n'+css+'\n</style>\n</head>',1)
    for marker in SAVED_CREDENTIALS:
        if marker not in result:fail("Protected academic or personal data missing after change")
    if any(photo in result for photo in OLD_PHOTOS):fail("Old portrait gallery photo remained")
    if result.count('class="mpw-sport-white-card ')!=3 or result.count(SOURCE)!=3:
        fail("Selected photo cards absent")
    if result.count("<main")!=1 or result.count("</main>")!=1:
        fail("Main landmark modified")
    if result.count("<h1")!=1:fail("H1 modified")
    if OLD_START in result or OLD_STYLE_ID in result:fail("Old gallery markup/styles remain")
    if len(result.encode("utf-8"))<20000:fail("Unexpected truncation")
    return result

def check():
    if not ROOT.is_dir() or ROOT.is_symlink():fail("Unexpected root")
    if not HT.is_file() or HT.is_symlink() or sha(HT.read_bytes())!=EXPECTED_HT:
        fail("Rewrite differs from pinned release")
    if not PAGE.is_file() or PAGE.is_symlink() or sha(PAGE.read_bytes())!=EXPECTED_PAGE:
        fail("Live profile differs from pinned source; refusing overwrite")
def install(run):
    run=run_id(run);check()
    path=stage(run);prior=backup(run);info=manifest(run)
    if not path.is_file() or path.is_symlink():fail("New source missing from private stage")
    if prior.exists() or prior.is_symlink() or info.exists():fail("Rollback artifact collision")
    previous=PAGE.read_bytes()
    rewritten=make_new(previous.decode("utf-8"),path.read_text("utf-8")).encode("utf-8")
    with open(prior,"xb") as f:
        os.chmod(prior,0o600)
        f.write(previous);f.flush();os.fsync(f.fileno())
    meta={"runid":run,"before":sha(previous),"after":sha(rewritten),"bytes":len(rewritten),
          "route":"/about/mojtaba-rozegar/","previous_images_removed":5,"selection_added":3}
    with open(info,"x",encoding="utf-8") as f:json.dump(meta,f)
    os.chmod(info,0o600)
    mode=stat.S_IMODE(PAGE.stat().st_mode)
    try:
        atomic(PAGE,rewritten,mode)
        if sha(PAGE.read_bytes())!=meta["after"]:fail("Post-write digest mismatch")
    except BaseException:
        if PAGE.is_file() and not PAGE.is_symlink() and sha(PAGE.read_bytes())==meta["after"]:
            atomic(PAGE,previous,mode)
        raise
    print(json.dumps({"result":"MOJPLAYWIN_PROFESSOR_SELECTED_PHOTOS_INSTALLED",
        "before_sha":meta["before"],"after_sha":meta["after"],
        "old_photos_removed":5,"selected_sports":2,"selected_white_shirt":1,
        "portrait_and_cv_preserved":True,"other_sites_untouched":True,
        "passenger_restarted":False,"private_backup_ready":True}))

def rollback(run):
    run=run_id(run);prior=backup(run);info=manifest(run)
    if not prior.is_file() or prior.is_symlink() or not info.is_file() or info.is_symlink():
        fail("Rollback artifacts missing")
    b=prior.read_bytes();meta=json.loads(info.read_text("utf-8"))
    if sha(b)!=EXPECTED_PAGE or meta.get("before")!=EXPECTED_PAGE:fail("Rollback data corrupt")
    current=PAGE.read_bytes()
    if sha(current)!=meta["after"]:fail("Refuse overwrite unrelated change")
    atomic(PAGE,b,stat.S_IMODE(PAGE.stat().st_mode))
    if sha(PAGE.read_bytes())!=EXPECTED_PAGE:fail("Rollback verification failed")
    print(json.dumps({"result":"MOJPLAYWIN_PROFESSOR_PHOTOS_RESTORED","sha256":EXPECTED_PAGE}))

if __name__=="__main__":
    if len(sys.argv)!=3:fail("Expected install|rollback RUN_ID")
    if sys.argv[1]=="install":install(sys.argv[2])
    elif sys.argv[1]=="rollback":rollback(sys.argv[2])
    else:fail("Invalid operation")
