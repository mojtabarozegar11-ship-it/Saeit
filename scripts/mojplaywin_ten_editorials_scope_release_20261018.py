#!/usr/bin/env python3
"""Atomic publication of 19 MojPlayWin editorial snapshots and 190 tiny WebPs.

Only GET of these 19 explicitly enumerated root-domain informational paths
is shadowed. Never change Django, Passenger, shared app, user data, checkout,
store, personal subsites, unrelated root rules or URL shapes. Strong SHA gate,
private byte-preserving backup and reversible exact insertion.
"""
import hashlib,json,os,re,stat,sys,tarfile,tempfile
from pathlib import Path
from shutil import rmtree

ROOT=Path("/home/zomorod2/mojplaywin.com")
HOME=ROOT.parent
HT=ROOT/".htaccess"
LIVE=ROOT/"design-preview-20261017/mpw-ten-editorials-20261018"
BEFORE_SHA="021c3b7c947f709cc39393fe6e84ba6e84c7e820122631a05c865d86e69aa464"
START="# MPW_ILLUSTRATED_TEN_PER_PAGE_20261018_BEGIN"
END="# MPW_ILLUSTRATED_TEN_PER_PAGE_20261018_END"
PATHS=(
 "/company/","/research/","/knowledge/","/industry/","/economy/",
 "/studio/","/market/","/agents/","/ventures/agriculture/",
 "/ventures/cafe-restaurant/","/ventures/fuel-station/",
 "/ventures/jewelry-gold/","/ventures/carpets/",
 "/ventures/currency-crypto/","/ventures/ecommerce/",
 "/ventures/hospitality/","/services/","/about/",
 "/about/mojtaba-rozegar/",
)
PUBLIC_BASE="design-preview-20261017/mpw-ten-editorials-20261018"
CHECK_IMAGES_MAX=36000
def stop(reason):raise RuntimeError(reason)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def id_ok(value):
    if not re.fullmatch(r"[0-9]{9,20}",value):stop("Unsafe run ID")
    return value
def slug(path):return "-".join(x for x in path.strip("/").split("/") if x)
def stage_path(run):return HOME/(".mpw-190-content-"+id_ok(run)+".tar.gz")
def backup_path(run):return HOME/(".mpw-190-rollback-"+id_ok(run))
def atomic(path,raw,mode):
    if path.is_symlink():stop("Unexpected symlink")
    fd,tmp=tempfile.mkstemp(prefix=".mpw-190-",dir=path.parent)
    try:
        os.fchmod(fd,mode)
        with os.fdopen(fd,"wb") as f:f.write(raw);f.flush();os.fsync(f.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
def rules():
    # Match the exact REQUEST_URI in the already-isolated MojPlayWin document root.
    # Its existing working About, professor and sector rules use the same shape.
    # HTTP_HOST is intentionally not relied on because the cPanel reverse proxy
    # can normalize it before per-directory mod_rewrite runs.
    result=[START]
    for path in PATHS:
        condition="^"+re.escape(path)+"$"
        target="/"+PUBLIC_BASE+"/pages/"+slug(path)+".html"
        result.extend((
          "RewriteCond %{REQUEST_METHOD} ^GET$",
          "RewriteCond %{REQUEST_URI} "+condition,
          "RewriteRule ^.*$ "+target+" [END,QSD]",
        ))
    result.append(END)
    return ("\n".join(result)+"\n").encode("ascii")
def patch_ht(raw):
    if sha(raw)!=BEFORE_SHA:stop("Root rewrite changed; refuse to modify")
    if not raw.count(b"RewriteEngine On")==1:stop("Unknown rewrite engine state")
    if START.encode() in raw or END.encode() in raw:stop("Already installed")
    if b"MPW_EXACT_ABOUT_80_20_20261018" not in raw:
        stop("Preserved main About route unexpectedly absent")
    if b"MPW_EXACT_LEADERSHIP_ROOZEGAR_20261018" not in raw:
        stop("Preserved professor About route unexpectedly absent")
    edited=raw.replace(b"RewriteEngine On",b"RewriteEngine On\n"+rules(),1)
    if edited.replace(b"\n"+rules(),b"",1)!=raw:stop("Rewrite not exactly reversible")
    for forbidden in ("/store/","/checkout/","/payment/","/admin/","/api/","/farnaz/","/saman/","/picm/","/mojtaba.roozegar/"):
        if any(route.startswith(forbidden) for route in PATHS):
            stop("Sensitive or child-site route unexpectedly included")
    if rules().count(b"RewriteRule")!=len(PATHS):stop("Rule count mismatch")
    return edited
def stage_archive(src,folder):
    with tarfile.open(src,mode="r:gz") as tar:
        files=[m for m in tar if m.isfile()]
        if len(files)!=210:stop("Unexpected archived file count (19 html +190 webp+manifest expected)")
        for item in files:
            if item.issym() or item.islnk() or item.size>950000:
                stop("Invalid member type or size")
            s=item.name.removeprefix("./")
            if not s or s.startswith("/") or any(part in (".","..","") for part in Path(s).parts):
                stop("Unsafe archive member path")
            if not (s=="manifest.json" or re.fullmatch(r"pages/[a-z0-9-]+\.html",s) or re.fullmatch(r"images/[a-z0-9-]+\.webp",s)):
                stop("Unexpected archive entry")
            target=folder/s
            target.parent.mkdir(parents=True,exist_ok=True)
            with tar.extractfile(item) as inf,open(target,"xb") as outf:
                while True:
                    chunk=inf.read(128000)
                    if not chunk:break
                    outf.write(chunk)
            target.chmod(0o644)
    manifest=json.loads((folder/"manifest.json").read_text("utf-8"))
    if set(manifest.get("paths",{}))!=set(PATHS):stop("Route whitelist differs")
    if len(manifest.get("images",{}))!=len(PATHS):stop("Missing image manifests")
    claimed=set()
    for path,info in manifest["paths"].items():
        item=folder/info["file"]
        if not item.is_file() or sha(item.read_bytes())!=info["sha256"]:stop("Page SHA verification failed "+path)
        txt=item.read_text("utf-8")
        if txt.count('class="mpw-ten-card"')!=10 or txt.count('id="mpw-ten-illustrated-20261018"')!=1:
            stop("Ten field notes missing from "+path)
        if "<form" in txt.lower() or "javascript:" in txt.lower():stop("Form or unsafe URL in static source "+path)
        for pic in manifest["images"][path]:
            pathstr=pic["file"];claimed.add(pathstr)
            img=folder/pathstr
            if not img.is_file() or img.stat().st_size>CHECK_IMAGES_MAX or sha(img.read_bytes())!=pic["sha256"]:
                stop("Compressed WebP content mismatch")
    if len(claimed)!=190:stop("Expected 190 distinct source images")
    found={p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file() and p.suffix==".webp"}
    if claimed!=found:stop("Unlisted image files")
    if sum(1 for p in (folder/"pages").glob("*.html"))!=19:stop("Unknown page count")
    return manifest

def safe_root():
    if not ROOT.is_dir() or ROOT.is_symlink() or not (ROOT/"design-preview-20261017").is_dir():
        stop("Root or static-preview directory missing")
    if not HT.is_file() or HT.is_symlink():stop("Root htaccess invalid")
    if LIVE.exists() or LIVE.is_symlink():stop("Editorial release folder already exists; no overwrite")
    if sha(HT.read_bytes())!=BEFORE_SHA:stop("Live rewrite hash has changed")
    if os.statvfs(ROOT).f_bavail*os.statvfs(ROOT).f_frsize<10000000:stop("Insufficient free filesystem blocks")
def install(run):
    run=id_ok(run);safe_root()
    source=stage_path(run);backup=backup_path(run)
    if not source.is_file() or source.is_symlink():stop("No private package available")
    if backup.exists() or backup.is_symlink():stop("Existing rollback location")
    if source.stat().st_size>10000000:stop("Package too large")
    before=HT.read_bytes();after=patch_ht(before)
    unpack=Path(tempfile.mkdtemp(prefix=".mpw-190-validated-",dir=ROOT/"design-preview-20261017"))
    installed=False
    backup.mkdir(mode=0o700)
    try:
        manifest=stage_archive(source,unpack)
        # tempfile.mkdtemp defaults to 0700: Apache cannot serve those files.
        # Set only the new public content directory and its known child directories to 0755.
        for public_dir in (unpack,unpack/"pages",unpack/"images"):
            if not public_dir.is_dir() or public_dir.is_symlink():stop("Unsafe public directory")
            public_dir.chmod(0o755)
        (backup/"original.htaccess").write_bytes(before)
        os.chmod(backup/"original.htaccess",0o600)
        meta={"runid":run,"before_sha":sha(before),"after_sha":sha(after),"rules":len(PATHS),
              "editorials":190,"images":190,"release_sha":sha((unpack/"manifest.json").read_bytes())}
        (backup/"manifest.json").write_text(json.dumps(meta),"utf-8")
        os.chmod(backup/"manifest.json",0o600)
        # New directory is not routed to until all package images and pages exist.
        os.replace(unpack,LIVE)
        installed=True
        atomic(HT,after,stat.S_IMODE(HT.stat().st_mode))
        if sha(HT.read_bytes())!=meta["after_sha"]:stop("Rewrite post-write checksum invalid")
    except BaseException:
        if sha(HT.read_bytes())==sha(after):
            atomic(HT,before,stat.S_IMODE(HT.stat().st_mode))
        if installed and LIVE.is_dir() and not LIVE.is_symlink():rmtree(LIVE)
        if unpack.is_dir() and not unpack.is_symlink():rmtree(unpack)
        (backup/"FAILED").write_text("failed\n")
        raise
    print(json.dumps({"status":"MPW_190_EDITS_19_ROUTES_INSTALLED",
      "routes":len(PATHS),"articles":190,"images":190,
      "ht_before":sha(before),"ht_after":sha(after),
      "images_budget_bytes":CHECK_IMAGES_MAX,"rollback_ready":True,
      "Passenger_restart":False,"store_orders_payments_untouched":True,
      "protected_subsite_routes_unchanged_by_exact_rules":True}))
def rollback(run):
    run=id_ok(run);backup=backup_path(run)
    if not backup.is_dir() or backup.is_symlink():stop("Backup directory unavailable")
    meta=json.loads((backup/"manifest.json").read_text("utf-8"))
    prior=(backup/"original.htaccess").read_bytes()
    if sha(prior)!=BEFORE_SHA or meta["before_sha"]!=BEFORE_SHA:stop("Corrupt rollback htaccess")
    current=HT.read_bytes()
    if sha(current)==meta["after_sha"]:
        atomic(HT,prior,stat.S_IMODE(HT.stat().st_mode))
    elif sha(current)!=BEFORE_SHA:stop("Concurrent htaccess modification; do not clobber")
    if LIVE.is_dir() and not LIVE.is_symlink():
        if sha((LIVE/"manifest.json").read_bytes())!=meta["release_sha"]:stop("Concurrent asset edits; do not remove")
        rmtree(LIVE)
    if sha(HT.read_bytes())!=BEFORE_SHA:stop("Rollback SHA failure")
    print(json.dumps({"status":"MPW_190_EDITS_ROLLED_BACK","ht_sha256":BEFORE_SHA,"asset_removed":not LIVE.exists()}))
if __name__=="__main__":
    if len(sys.argv)!=3:stop("Usage install|rollback runid")
    if sys.argv[1]=="install":install(sys.argv[2])
    elif sys.argv[1]=="rollback":rollback(sys.argv[2])
    else:stop("Unsupported mode")
