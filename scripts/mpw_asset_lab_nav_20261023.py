#!/usr/bin/env python3
"""One guarded discovery card on the already-owned MojPlayWin products PHP route.
Pre/post SHA, strict marker and path validation, PHP lint, exact rollback.
"""
import fcntl,hashlib,json,os,pwd,re,shutil,stat,subprocess,sys
from pathlib import Path
HOME=Path("/home/zomorod2")
SITE=HOME/"mojplaywin.com"
SHELL=SITE/"design-preview-20261017"/"_mpw_dynamic_main_shell_20261019.php"
HTACCESS=SITE/".htaccess"
PRIVATE=HOME/".private_mpw_assetlab_nav_20261023"
HTACCESS_SHA="6d06dc358b118ca59843941cd79c627eb4792a3584b0d11b4de7ed49b8552b63"
RELEASE="ASSETLAB-20261023-01"
MARK="MPW_ASSETLAB_MAIN_NAV_20261023"
NAV="ASSETLAB-MAIN-NAV-20261023-01"
PHP_ADD=r"""
// MPW_ASSETLAB_MAIN_NAV_20261023_BEGIN
// Narrow new product discovery card only. Existing content and routes unchanged.
if ($slug === 'products' &&
    strpos($rendered, 'id="mpw-assetlab-main-discovery-20261023"') === false &&
    strpos($rendered, 'id="mpw-nextwave-main-discovery-20261023"') !== false &&
    preg_match_all('~</main\s*>~i', $rendered) === 1) {
    $assetLabCard = <<<'MPW_ASSETLAB_CARD'
<section id="mpw-assetlab-main-discovery-20261023" data-assetlab-version="ASSETLAB-20261023-01" data-navigation-version="ASSETLAB-MAIN-NAV-20261023-01" aria-label="MojPlayWin free image optimization tool" style="margin:24px 0;padding:clamp(16px,3vw,25px);background:#10283a;color:#eef9ff;border:1px solid #4b8c91;border-radius:18px">
<div style="display:flex;flex-wrap:wrap;align-items:center;gap:18px">
<img src="/mpw-editorial/asset-lab/20261023/assets/convert.webp" width="180" height="101" loading="lazy" decoding="async" alt="Original WebP conversion diagram with source image and compact output" style="width:180px;max-width:100%;height:auto;border-radius:12px">
<div style="flex:1;min-width:min(100%,220px)">
<p style="color:#8ef2d8;font-weight:850;margin:0 0 6px">NEW FREE INTERACTIVE TOOL</p>
<h2 style="color:#ffda9b;margin:0 0 7px">Image Delivery Lab</h2>
<p style="color:#c4dce5;margin:0 0 12px">Convert images into real WebP variants locally, compare actual bytes, download optimized files and copy accessible responsive HTML. No upload or account required.</p>
<a href="/mpw-editorial/asset-lab/20261023/index.html" style="display:inline-block;background:#80efd1;color:#062b33;padding:11px 17px;border-radius:10px;font-weight:850;text-decoration:none">Open Image Delivery Lab →</a>
</div></div></section>
MPW_ASSETLAB_CARD;
    $assetLabCount = 0;
    $assetLabResult = preg_replace_callback('~</main\s*>~i',
        static function(array $match) use ($assetLabCard): string {
            return "\n" . $assetLabCard . "\n" . $match[0];
        }, $rendered, 1, $assetLabCount);
    if ($assetLabCount === 1 && is_string($assetLabResult) &&
        substr_count($assetLabResult, 'id="mpw-assetlab-main-discovery-20261023"') === 1) {
        $rendered = $assetLabResult;
    }
}
// MPW_ASSETLAB_MAIN_NAV_20261023_END
"""
def sha(b):return hashlib.sha256(b).hexdigest()
def patch(src):
    if "// "+MARK+"_BEGIN" in src:
        if src.count("// "+MARK+"_BEGIN")==1 and src.count("// "+MARK+"_END")==1:return src,False
        raise RuntimeError("Unexpected existing Asset Lab patch")
    if "// MPW_NEXTWAVE_MAIN_NAV_20261023_END" not in src or "// MPW_ARCADE_MAIN_DISCOVERY_20261023_END" not in src:
        raise RuntimeError("Previous verified navigation markers missing")
    anchor="\necho $rendered;"
    if src.count(anchor)!=1 or not src.rstrip().endswith("echo $rendered;"):
        raise RuntimeError("Unexpected PHP rendering anchor")
    return src.replace(anchor,"\n"+PHP_ADD.strip("\n")+"\n"+anchor,1),True
def lint(path):
    php=shutil.which("php") or next((p for p in ("/opt/cpanel/ea-php83/root/usr/bin/php","/opt/cpanel/ea-php82/root/usr/bin/php") if Path(p).is_file()),None)
    if not php:raise RuntimeError("PHP CLI missing")
    r=subprocess.run([php,"-l",str(path)],capture_output=True,text=True,timeout=25)
    if r.returncode!=0 or "No syntax errors detected" not in r.stdout+r.stderr:
        raise RuntimeError("PHP lint failed: "+(r.stdout+r.stderr)[:500])
def write(p,b):
    with open(p,"xb") as f:f.write(b);f.flush();os.fsync(f.fileno())
    os.chmod(p,0o600)
def preflight():
    if pwd.getpwuid(os.getuid()).pw_name!="zomorod2":raise RuntimeError("Wrong cPanel account")
    for p in (HOME,SITE,SHELL.parent,SHELL,HTACCESS):
        if not p.exists() or p.is_symlink() or p.stat().st_uid!=os.getuid():
            raise RuntimeError("Unexpected owner: "+str(p))
    if sha(HTACCESS.read_bytes())!=HTACCESS_SHA:raise RuntimeError("Protected routing SHA drift")
    if not 1000<SHELL.stat().st_size<120000:raise RuntimeError("Unexpected PHP source size")
    root=SITE/"mpw-editorial/asset-lab/20261023"
    manifest=root/"release.json"
    if not manifest.is_file() or manifest.is_symlink() or json.loads(manifest.read_text()).get("release_id")!=RELEASE:
        raise RuntimeError("New public release not installed")
    for name in ("index.html","assets/convert.webp","assets/budget.webp","assets/responsive.webp"):
        p=root/name
        if not p.is_file() or p.is_symlink():raise RuntimeError("Missing original release asset "+name)
def operate(action,run,commit):
    if not re.fullmatch(r"[0-9]{8,20}",run) or not re.fullmatch(r"[a-f0-9]{40}",commit):
        raise RuntimeError("Invalid run identity")
    preflight()
    PRIVATE.mkdir(mode=0o700,exist_ok=True)
    if PRIVATE.is_symlink() or PRIVATE.stat().st_uid!=os.getuid() or PRIVATE.stat().st_dev!=SHELL.stat().st_dev:
        raise RuntimeError("Unsafe backup directory")
    with open(PRIVATE/"lock","a+") as handle:
        fcntl.flock(handle,fcntl.LOCK_EX)
        old=SHELL.read_bytes()
        receipt=PRIVATE/("receipt-"+run+".json")
        backup=PRIVATE/("backup-"+run+".php")
        if action=="install":
            if receipt.exists() or receipt.is_symlink():raise RuntimeError("Duplicate receipt")
            candidate,changed=patch(old.decode("utf8"))
            if not changed:raise RuntimeError("Already installed")
            new=candidate.encode("utf8")
            draft=PRIVATE/("candidate-"+run+".php")
            write(draft,new);lint(draft)
            write(backup,old)
            info={"release_id":RELEASE,"nav_version":NAV,"run":run,"commit":commit,"pre_sha256":sha(old),"post_sha256":sha(new)}
            write(receipt,json.dumps(info,sort_keys=True).encode())
            if sha(SHELL.read_bytes())!=info["pre_sha256"]:raise RuntimeError("Concurrent PHP modification")
            os.chmod(draft,stat.S_IMODE(SHELL.stat().st_mode))
            os.replace(draft,SHELL)
            if sha(SHELL.read_bytes())!=info["post_sha256"]:raise RuntimeError("Post-switch PHP SHA mismatch")
            print("ASSETLAB_NAV_ATOMIC_INSTALL",json.dumps(info,sort_keys=True))
        elif action=="rollback":
            if not receipt.is_file() or receipt.is_symlink() or not backup.is_file() or backup.is_symlink():
                raise RuntimeError("Rollback provenance absent")
            info=json.loads(receipt.read_text())
            if info.get("run")!=run or info.get("commit")!=commit or info.get("release_id")!=RELEASE:
                raise RuntimeError("Rollback identity mismatch")
            if sha(old)!=info["post_sha256"] or sha(backup.read_bytes())!=info["pre_sha256"]:
                raise RuntimeError("Concurrent modification: refuse rollback")
            draft=PRIVATE/("restore-"+run+".php")
            write(draft,backup.read_bytes());lint(draft)
            os.chmod(draft,stat.S_IMODE(SHELL.stat().st_mode))
            os.replace(draft,SHELL)
            if sha(SHELL.read_bytes())!=info["pre_sha256"]:raise RuntimeError("Rollback SHA mismatch")
            print("ASSETLAB_NAV_EXACT_ROLLBACK_PASS")
        else:raise RuntimeError("Invalid command")
def selftest():
    fixture="<?php\n// MPW_ARCADE_MAIN_DISCOVERY_20261023_END\n// MPW_NEXTWAVE_MAIN_NAV_20261023_END\n$slug='products';$rendered='<main><h1>Products</h1></main>';\necho $rendered;\n"
    new,changed=patch(fixture)
    assert changed and new.count("// "+MARK+"_BEGIN")==1
    again,changed=patch(new)
    assert not changed and again==new
    assert 'href="/mpw-editorial/asset-lab/20261023/index.html"' in new
    for broken in (fixture.replace("echo $rendered;","print $rendered;"),fixture.replace("MPW_NEXTWAVE_MAIN_NAV_20261023_END","missing")):
        try:patch(broken)
        except RuntimeError:pass
        else:raise AssertionError("Invalid fixture accepted")
    from tempfile import TemporaryDirectory
    with TemporaryDirectory() as t:
        p=Path(t)/"fixture.php";p.write_text(new);lint(p)
    print("ASSETLAB_NAV_SELFTEST_PASS")
if __name__=="__main__":
    if sys.argv[1:]==["selftest"]:selftest()
    elif len(sys.argv)==4:operate(*sys.argv[1:])
    else:raise SystemExit("selftest | install RUN SHA | rollback RUN SHA")
