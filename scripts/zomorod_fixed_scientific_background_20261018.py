#!/usr/bin/env python3
"""Isolated, reversible change: fixed background on the Zomorod root homepage only."""
import hashlib, json, os, pwd, re, sys, tempfile
from pathlib import Path

ROOT=Path("/home/zomorod2/public_html")
HOME=ROOT/"index.html"
IMAGE=ROOT/"static/site/backgrounds/zomorod-fixed-cosmos-20261018.webp"
BACKUPS=Path("/home/zomorod2/.backups/zomorod-fixed-background-20261018")
MARKER='zm-fixed-scientific-background-20261018'
CSS="""<style id="zm-fixed-scientific-background-20261018">
/* Only root home page background; original content, layout and animations stay intact. */
html {background-color:#04180f!important}
body {
  background-color:#04180f!important;
  background-image:url('/static/site/backgrounds/zomorod-fixed-cosmos-20261018.webp')!important;
  background-position:center center!important;
  background-repeat:no-repeat!important;
  background-size:cover!important;
  background-attachment:fixed!important;
}
/* On mobile, keep the same fixed backdrop independent of content scrolling. */
@media(max-width:767px){
  body {background-position:center center!important;background-size:cover!important}
}
</style>
"""
def sha(data):return hashlib.sha256(data).hexdigest()
def ensure():
    assert pwd.getpwuid(os.getuid()).pw_name=="zomorod2","Incorrect hosting user"
    assert ROOT.is_dir() and not ROOT.is_symlink()
    assert HOME.is_file() and not HOME.is_symlink()
    assert IMAGE.parent.is_dir() and not IMAGE.parent.is_symlink()
def runpath(run):
    assert re.fullmatch(r"[0-9]{1,20}",run),"Bad run id"
    return BACKUPS/run
def atomic(path,data,mode):
    fd,name=tempfile.mkstemp(prefix=".zm-bg-",dir=path.parent)
    try:
        with os.fdopen(fd,"wb") as f:
            f.write(data);f.flush();os.fsync(f.fileno())
        os.chmod(name,mode)
        os.replace(name,path)
    finally:
        if os.path.exists(name):os.unlink(name)
def transform(raw):
    html=raw.decode("utf-8")
    assert MARKER not in html,"Background already installed; no duplicate"
    assert len(raw)>1500000,"Unexpected or incomplete homepage"
    assert html.count("</head>")==1 and html.count("</body>")==1
    for key in ('id="solar-stage"','id="orbital-cards"','id="site-footer"','ZOMOROD_ORBIT_DATA'):
        assert key in html,"Expected live home marker missing: "+key
    new=html.replace("</head>",CSS+"</head>",1).encode("utf-8")
    assert new.replace(CSS.encode("utf-8"),b"",1)==raw,"Unrelated HTML changed"
    return new
def selftest():
    mock=('<html><head></head><body><div id="solar-stage"></div><div id="orbital-cards"></div><footer id="site-footer"></footer><script>ZOMOROD_ORBIT_DATA</script></body></html>'+'X'*1600000).encode()
    out=transform(mock)
    assert out.replace(CSS.encode(),b"",1)==mock and out.count(MARKER.encode())==1
    print("BACKGROUND_PATCH_SELFTEST=passed")
def install(run,stage):
    ensure()
    dest=runpath(run)
    assert not dest.exists() and not dest.is_symlink()
    stage=Path(stage)
    assert stage.is_file() and not stage.is_symlink()
    photo=stage.read_bytes()
    assert len(photo)>10000 and photo[:4]==b"RIFF" and photo[8:12]==b"WEBP","Asset invalid"
    assert not IMAGE.exists() and not IMAGE.is_symlink(),"Asset name already exists; refusing overwrite"
    original=HOME.read_bytes()
    updated=transform(original)
    dest.mkdir(parents=True,mode=0o700)
    atomic(dest/"index.before.html",original,0o600)
    assert sha((dest/"index.before.html").read_bytes())==sha(original)
    meta={"before":sha(original),"after":sha(updated),"image":sha(photo),"mode":HOME.stat().st_mode&0o777}
    (dest/"manifest.json").write_text(json.dumps(meta),encoding="utf-8")
    atomic(IMAGE,photo,0o644)
    assert sha(IMAGE.read_bytes())==meta["image"]
    atomic(HOME,updated,meta["mode"])
    assert sha(HOME.read_bytes())==meta["after"]
    print("BACKGROUND_DEPLOYED=yes")
    print("HOMEPAGE_BACKUP_SHA256="+meta["before"])
    print("IMAGE_SHA256="+meta["image"])
def verify(run):
    ensure();p=runpath(run)
    meta=json.loads((p/"manifest.json").read_text())
    assert sha(HOME.read_bytes())==meta["after"]
    assert sha(IMAGE.read_bytes())==meta["image"]
    assert HOME.read_bytes().replace(CSS.encode(),b"",1)==(p/"index.before.html").read_bytes()
    print("ONLY_BACKGROUND_DIFF_CONFIRMED=yes")
def rollback(run):
    ensure();p=runpath(run)
    meta=json.loads((p/"manifest.json").read_text())
    old=(p/"index.before.html").read_bytes()
    assert sha(old)==meta["before"]
    actual=sha(HOME.read_bytes())
    if actual==meta["after"]:
        atomic(HOME,old,meta["mode"])
        print("HOMEPAGE_ROLLBACK_DONE=yes")
    elif actual!=meta["before"]:
        raise RuntimeError("Concurrent homepage change; no unsafe overwrite")
    if IMAGE.exists() and sha(IMAGE.read_bytes())==meta["image"]:
        IMAGE.unlink()
        print("NEW_BACKGROUND_IMAGE_REMOVED=yes")
if __name__=="__main__":
    if sys.argv[1:]==["selftest"]:selftest()
    elif len(sys.argv)==4 and sys.argv[1]=="install":install(sys.argv[2],sys.argv[3])
    elif len(sys.argv)==3 and sys.argv[1]=="verify":verify(sys.argv[2])
    elif len(sys.argv)==3 and sys.argv[1]=="rollback":rollback(sys.argv[2])
    else:raise SystemExit("selftest | install RUN_ID STAGED_WEBP | verify RUN_ID | rollback RUN_ID")
