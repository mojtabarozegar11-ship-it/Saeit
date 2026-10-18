#!/usr/bin/env python3
"""Exact personal V17 HOME 'New perspectives' replacement, preserving all other content.

Replace the three unwanted cards (executive 01, executive 10, four-view
composite 09) with three individually framed original photo-09 perspectives:
sport/casual panel one, outdoor sport jacket panel four, white shirt panel three.
Only edits the independent personal site's home.html template; no photo bytes,
other templates, shared Django, commerce, databases, or root rewrites are touched.
"""
import hashlib,json,os,re,stat,sys,tempfile
from pathlib import Path

APP=Path("/home/zomorod2/mojtaba_personal/mojtaba_roozegar_personal_v17")
PAGE=APP/"templates/personal_site/core/home.html"
PHOTO=APP/"static/personal_site/owner_gallery_20261015_b/photo-09.png"
PHOTO_SHA="44b6a033b63568e748ed8464343c2feabd587471013aa3104f68ab44747bcfb8"
MARKER='id="mpw-new-originals-20261015-b"'
NEW_MARKER='id="mpw-personal-home-sport-white-20261018"'
PHOTO_TAG="{% static 'personal_site/owner_gallery_20261015_b/photo-09.png' %}"
SOURCE_CAPTIONS=("Personal executive portrait","Executive close-up portrait","Four professional portrait views")
SUBDIR=Path("/home/zomorod2/.backups/mojtaba-personal-home-sport-white-20261018")
STRIP_PATTERN=re.compile(r'<section\b[^>]*\bid="mpw-new-originals-20261015-b"[^>]*>.*?</section>',re.I|re.S)
CARDS=(
  ("sport-one","Casual sport portrait","0%"),
  ("sport-four","Outdoor sport-jacket portrait","-75%"),
  ("white-shirt","White-shirt portrait","-50%"),
)

def digest(data):return hashlib.sha256(data).hexdigest()
def problem(txt):raise RuntimeError(txt)
def only_run(v):
    if not re.fullmatch(r"[0-9]{9,20}",v):problem("Invalid run ID")
    return v

def build_replacement():
    items=[]
    for css,title,x in CARDS:
        items.append(
            '<figure class="mpw-portrait-card '+css+'"><div class="mpw-crop-frame" role="img" aria-label="'+title+'">'
            '<img src="'+PHOTO_TAG+'" loading="lazy" decoding="async" alt="'+title+'" '
            'style="--sport-photo-x:'+x+'" width="1600" height="640"></div>'
            '<figcaption>'+title+'</figcaption></figure>'
        )
    css="""<style id="mpw-personal-home-sport-crops-20261018">
#mpw-personal-home-sport-white-20261018{max-width:1180px;margin:35px auto;padding:clamp(14px,2.2vw,26px);border:1px solid #a78c59;border-radius:12px;background:#172839;color:#f1e9dc;box-sizing:border-box}
#mpw-personal-home-sport-white-20261018 *{box-sizing:border-box}
#mpw-personal-home-sport-white-20261018 h2{font:400 clamp(23px,3vw,36px)/1.25 Georgia,serif;color:#f8e7c8;margin:0 0 14px}
#mpw-personal-home-sport-white-20261018 .mpw-sport-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:clamp(8px,1.6vw,18px)}
#mpw-personal-home-sport-white-20261018 .mpw-portrait-card{margin:0;min-width:0;border:1px solid rgba(215,183,104,.38);border-radius:14px;overflow:hidden;background:#101e2e}
#mpw-personal-home-sport-white-20261018 .mpw-crop-frame{position:relative;width:100%;aspect-ratio:4/5;overflow:hidden;background:#121820}
#mpw-personal-home-sport-white-20261018 .mpw-crop-frame img{display:block;position:absolute;left:0;top:50%;width:400%;height:auto;max-width:none;transform:translate(var(--sport-photo-x),-50%);object-fit:unset}
#mpw-personal-home-sport-white-20261018 figcaption{padding:9px 12px;color:#f1e9dc;font-size:clamp(12px,1.4vw,15px);line-height:1.5}
@media(max-width:620px){#mpw-personal-home-sport-white-20261018{margin:20px auto;padding:12px}#mpw-personal-home-sport-white-20261018 .mpw-sport-grid{grid-template-columns:repeat(2,minmax(0,1fr));gap:9px}#mpw-personal-home-sport-white-20261018 .white-shirt{grid-column:1/-1;width:min(50%,260px);justify-self:center}#mpw-personal-home-sport-white-20261018 figcaption{padding:8px;font-size:12px}}
</style>"""
    return ('<section '+NEW_MARKER+' aria-label="Selected casual and white-shirt photographs">'
            +css+'<h2>Personal portraits · Casual &amp; white-shirt perspectives</h2>'
            +'<div class="mpw-sport-grid">'+''.join(items)+'</div></section>')

def patch(old):
    if old.count(MARKER)!=1 or NEW_MARKER in old:problem("Original home gallery marker changed or already replaced")
    match=STRIP_PATTERN.search(old)
    if not match:problem("Expected first-generation source block missing")
    prior=match.group()
    for name in SOURCE_CAPTIONS:
        if prior.count(name)!=2:problem("Old screenshot caption occurrence mismatch: "+name)
    if prior.count('<figure>')!=3 or prior.count('<img ' )!=3:
        problem("Home gallery has unexpected number of cards; no overwrite")
    if any(tag not in prior for tag in ("photo-01.png","photo-10.png","photo-09.png")):
        problem("Photo source map no longer matches screenshot")
    candidate=old[:match.start()]+build_replacement()+old[match.end():]
    if candidate.count(NEW_MARKER)!=1 or MARKER in candidate:problem("Bad section replacement")
    if candidate.count('class="mpw-portrait-card')!=3 or candidate.count(PHOTO_TAG)!=3:
        problem("Photo count mismatch")
    if any(title in candidate[match.start():match.start()+4800] for title in SOURCE_CAPTIONS):
        problem("Unwanted black-suit or composite captions still present")
    if "{% block content %}" not in candidate or "{% endblock %}" not in candidate:
        problem("Django template landmarks lost")
    if len(candidate)<1000:problem("Unexpectedly small output")
    return candidate

def check():
    if not APP.is_dir() or APP.is_symlink() or not (APP/"manage.py").is_file():
        problem("Not isolated personal V17 Django application")
    if not PAGE.is_file() or PAGE.is_symlink():problem("Personal homepage template missing")
    if not PHOTO.is_file() or PHOTO.is_symlink() or digest(PHOTO.read_bytes())!=PHOTO_SHA:
        problem("Original four-view source photo missing or corrupted")
    if (APP/"templates/personal_site/core/gallery.html").is_symlink():
        problem("Unexpected other-template symlink")

def atomic(path,blob):
    fd,p=tempfile.mkstemp(prefix=".mpw-personal-sport-",dir=path.parent)
    try:
        os.fchmod(fd,stat.S_IMODE(path.stat().st_mode))
        with os.fdopen(fd,"wb") as f:f.write(blob);f.flush();os.fsync(f.fileno())
        os.replace(p,path)
    finally:
        if os.path.exists(p):os.unlink(p)

def restart_personal_only():
    p=APP/"tmp/restart.txt"
    if p.parent.is_dir() and not p.parent.is_symlink() and not p.is_symlink():
        p.touch()
        return True
    return False

def install(run):
    check();run=only_run(run)
    old=PAGE.read_bytes();new=patch(old.decode("utf-8")).encode()
    b=SUBDIR/run
    if b.exists() or b.is_symlink():problem("Rollback folder collision")
    b.mkdir(parents=True,mode=0o700)
    (b/"home.html").write_bytes(old)
    os.chmod(b/"home.html",0o600)
    info={"before_sha":digest(old),"after_sha":digest(new),"orig_photo_sha":PHOTO_SHA}
    (b/"manifest.json").write_text(json.dumps(info))
    os.chmod(b/"manifest.json",0o600)
    try:
        atomic(PAGE,new)
        if digest(PAGE.read_bytes())!=info["after_sha"]:problem("Post-patch SHA mismatch")
        restarted=restart_personal_only()
    except BaseException:
        if PAGE.is_file() and digest(PAGE.read_bytes())==info["after_sha"]:
            atomic(PAGE,old)
            restart_personal_only()
        raise
    print(json.dumps({"result":"PERSONAL_HOME_SPORT_WHITE_INSTALLED","sha_before":digest(old),
          "sha_after":digest(new),"sport_cards":2,"white_shirt_cards":1,
          "black_suit_cards_removed":2,"four_view_composite_card_removed":True,
          "other_templates_unchanged":True,"personal_v17_restart_only":restarted}))

def rollback(run):
    check();run=only_run(run)
    b=SUBDIR/run
    if not b.is_dir() or b.is_symlink():problem("No backup directory")
    before=(b/"home.html").read_bytes()
    manifest=json.loads((b/"manifest.json").read_text())
    if digest(before)!=manifest["before_sha"]:problem("Backup corruption")
    if digest(PAGE.read_bytes())!=manifest["after_sha"]:problem("Concurrent edits; refuse rollback over changed page")
    atomic(PAGE,before);restart_personal_only()
    if digest(PAGE.read_bytes())!=manifest["before_sha"]:problem("Rollback failed")
    print(json.dumps({"result":"PERSONAL_HOME_SPORT_WHITE_ROLLED_BACK","sha":manifest["before_sha"]}))

if __name__=="__main__":
    if len(sys.argv)!=3:problem("Usage install|rollback RUN_ID")
    if sys.argv[1]=="install":install(sys.argv[2])
    elif sys.argv[1]=="rollback":rollback(sys.argv[2])
    else:problem("Bad mode")
