#!/usr/bin/env python3
"""Guarded Nextwave discovery-card installation on MojPlayWin's two existing PHP GET routes.

Bounded one-file change, exact SHA preconditions, atomic switch, backup/rollback.
Does not change .htaccess, Django/Passenger, root, Arcade Lab, or any other path.
"""
import fcntl, hashlib, json, os, pwd, re, shutil, stat, subprocess, sys
from pathlib import Path
HOME=Path("/home/zomorod2")
SITE=HOME/"mojplaywin.com"
SHELL=SITE/"design-preview-20261017"/"_mpw_dynamic_main_shell_20261019.php"
HTACCESS=SITE/".htaccess"
PRIVATE=HOME/".private_mpw_nextwave_navigation_20261023"
PRE_SHA="dd2bdbca509560e640fe7c67bb60443bf6cc2663fcac46af1c90b1d62ab834cc"
ROUTING_SHA="6d06dc358b118ca59843941cd79c627eb4792a3584b0d11b4de7ed49b8552b63"
RELEASE="NEXTWAVE-20261023-01"
MARK="MPW_NEXTWAVE_MAIN_NAV_20261023"
NAV_VERSION="NEXTWAVE-MAIN-NAV-20261023-01"
PHP_ADD=r"""
// MPW_NEXTWAVE_MAIN_NAV_20261023_BEGIN
// Keep all existing PHP rendering intact; only append one bounded section
// to the two already-authorized routes when the earlier Arcade Lab card exists.
if (($slug === 'games' || $slug === 'products') &&
    strpos($rendered, 'id="mpw-nextwave-main-discovery-20261023"') === false &&
    strpos($rendered, 'id="mpw-arcade-main-discovery-20261023"') !== false) {
    $nextwaveCue = ($slug === 'games') ? 'First Realm' : 'Digital Products';
    if (strpos($rendered, $nextwaveCue) !== false &&
        preg_match_all('~</main\s*>~i', $rendered) === 1) {
        if ($slug === 'games') {
            $nextwaveCard = <<<'MPW_NEXTWAVE_GAME'
<section id="mpw-nextwave-main-discovery-20261023" data-nextwave-version="NEXTWAVE-20261023-01" data-navigation-version="NEXTWAVE-MAIN-NAV-20261023-01" aria-label="New MojPlayWin Orbit Switch game" style="margin:22px 0;padding:clamp(16px,3vw,25px);background:#101d35;color:#f0f7ff;border:1px solid #4a728a;border-radius:18px">
  <div style="display:flex;flex-wrap:wrap;align-items:center;gap:16px">
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 180 120" width="180" height="120" role="img" aria-label="Orbit Switch game cover showing two neon rings and a spacecraft" style="max-width:100%;height:auto;border-radius:12px;background:#061023" focusable="false"><circle cx="90" cy="60" r="49" fill="none" stroke="#76ebd0" stroke-width="4"/><circle cx="90" cy="60" r="30" fill="none" stroke="#6f8cbd" stroke-width="3"/><circle cx="90" cy="60" r="9" fill="#ffd190"/><path d="M139 51l19 9-19 9-6-9z" fill="#a2ffec"/><circle cx="65" cy="91" r="8" fill="#ff729c"/></svg>
    <div style="flex:1;min-width:min(100%,205px)"><p style="margin:0 0 5px;color:#80ead9;font-weight:800">NEW ORIGINAL GAME · 200 STAGES</p><h2 style="margin:0 0 8px;color:#ffdda9">Orbit Switch</h2><p style="margin:0 0 10px;color:#c4d6e4">Switch between two orbits, avoid hazards and save your stage progress. Touch and keyboard controls.</p><a href="/mpw-editorial/nextwave/20261023/orbit-switch/index.html" style="display:inline-block;background:#75ebce;color:#092334;padding:11px 16px;border-radius:10px;font-weight:800;text-decoration:none">Play Orbit Switch →</a></div>
  </div>
  <p style="margin:13px 0 0"><a href="/mpw-editorial/nextwave/20261023/index.html" style="color:#ffe4b4">Browse all Nextwave releases →</a></p>
</section>
MPW_NEXTWAVE_GAME;
        } else {
            $nextwaveCard = <<<'MPW_NEXTWAVE_TOOL'
<section id="mpw-nextwave-main-discovery-20261023" data-nextwave-version="NEXTWAVE-20261023-01" data-navigation-version="NEXTWAVE-MAIN-NAV-20261023-01" aria-label="New MojPlayWin Frame Budget Lab performance tool" style="margin:22px 0;padding:clamp(16px,3vw,25px);background:#101d35;color:#f0f7ff;border:1px solid #4a728a;border-radius:18px">
  <div style="display:flex;flex-wrap:wrap;align-items:center;gap:16px">
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 180 120" width="180" height="120" role="img" aria-label="Frame Budget Lab cover with CPU GPU timing bars and performance chart" style="max-width:100%;height:auto;border-radius:12px;background:#061023" focusable="false"><rect x="15" y="13" width="150" height="94" rx="12" fill="#112540" stroke="#78ebcf" stroke-width="2"/><rect x="28" y="31" width="65" height="9" rx="3" fill="#6fe8cf"/><rect x="28" y="50" width="107" height="9" rx="3" fill="#ffd28e"/><path d="M28 88l29-18 25 8 24-24 44 13" fill="none" stroke="#abb8ff" stroke-width="4"/></svg>
    <div style="flex:1;min-width:min(100%,205px)"><p style="margin:0 0 5px;color:#80ead9;font-weight:800">NEW INTERACTIVE TOOL</p><h2 style="margin:0 0 8px;color:#ffdda9">Frame Budget Lab</h2><p style="margin:0 0 10px;color:#c4d6e4">Estimate CPU and GPU timing, compare frame-rate budgets and export your scenario to CSV or JSON.</p><a href="/mpw-editorial/nextwave/20261023/frame-budget-lab/index.html" style="display:inline-block;background:#75ebce;color:#092334;padding:11px 16px;border-radius:10px;font-weight:800;text-decoration:none">Launch Frame Budget Lab →</a></div>
  </div>
  <p style="margin:13px 0 0"><a href="/mpw-editorial/nextwave/20261023/index.html" style="color:#ffe4b4">Browse all Nextwave releases →</a></p>
</section>
MPW_NEXTWAVE_TOOL;
        }
        $nextwaveCount = 0;
        $nextwaveOut = preg_replace_callback('~</main\s*>~i',
            static function(array $match) use ($nextwaveCard): string {
                return "\n" . $nextwaveCard . "\n" . $match[0];
            }, $rendered, 1, $nextwaveCount);
        if ($nextwaveCount === 1 && is_string($nextwaveOut) &&
            substr_count($nextwaveOut, 'id="mpw-nextwave-main-discovery-20261023"') === 1) {
            $rendered = $nextwaveOut;
        }
    }
}
// MPW_NEXTWAVE_MAIN_NAV_20261023_END
"""
def checksum(b):return hashlib.sha256(b).hexdigest()
def patch(s):
    if "// "+MARK+"_BEGIN" in s:
        if s.count("// "+MARK+"_BEGIN")==1 and s.count("// "+MARK+"_END")==1:return s,False
        raise RuntimeError("Unexpected existing Nextwave marker")
    tail="\necho $rendered;"
    if s.count(tail)!=1 or not s.rstrip().endswith("echo $rendered;"):
        raise RuntimeError("Unknown ending render anchor")
    if "// MPW_ARCADE_MAIN_DISCOVERY_20261023_END" not in s:
        raise RuntimeError("Existing approved Arcade Lab patch absent")
    return s.replace(tail,"\n"+PHP_ADD.strip("\n")+"\n"+tail,1),True
def preflight():
    if pwd.getpwuid(os.getuid()).pw_name!="zomorod2":raise RuntimeError("Unexpected server user")
    for p in (HOME,SITE,SHELL.parent,SHELL,HTACCESS):
        if not p.exists() or p.is_symlink() or p.stat().st_uid!=os.getuid():
            raise RuntimeError("Unexpected ownership or path: "+str(p))
    if checksum(HTACCESS.read_bytes())!=ROUTING_SHA:raise RuntimeError("Protected htaccess hash changed")
    if SHELL.stat().st_size>90000:raise RuntimeError("Oversize PHP shell")
    release=SITE/"mpw-editorial/nextwave/20261023"
    manifest=release/"release.json"
    if manifest.is_symlink() or not manifest.is_file() or json.loads(manifest.read_text())["release_id"]!=RELEASE:
        raise RuntimeError("Required publicly released Nextwave manifest absent")
    for rel in ("index.html","orbit-switch/index.html","frame-budget-lab/index.html"):
        p=release/rel
        if p.is_symlink() or not p.is_file() or p.stat().st_size<100:
            raise RuntimeError("Untrusted or missing original Nextwave release")
def php_lint(p):
    php=shutil.which("php")
    if not php:
        php=next((p for p in ("/opt/cpanel/ea-php83/root/usr/bin/php","/opt/cpanel/ea-php82/root/usr/bin/php","/opt/cpanel/ea-php81/root/usr/bin/php") if Path(p).is_file()),None)
    if not php:raise RuntimeError("PHP CLI not installed")
    test=subprocess.run([php,"-l",str(p)],timeout=25,capture_output=True,text=True)
    if test.returncode!=0 or "No syntax errors detected" not in test.stdout+test.stderr:
        raise RuntimeError("Candidate PHP lint failed: "+(test.stdout+test.stderr)[:600])
    print("NEXTWAVE_MAIN_PHP_LINT_PASS")
def write_new(p,b):
    if p.exists() or p.is_symlink():raise RuntimeError("Private run collision: "+str(p))
    with open(p,"xb") as f:f.write(b);f.flush();os.fsync(f.fileno())
    os.chmod(p,0o600)
def run(action,number,gitsha):
    if not re.fullmatch(r"[0-9]{8,20}",number) or not re.fullmatch(r"[0-9a-f]{40}",gitsha):
        raise RuntimeError("Invalid run/commit")
    preflight()
    PRIVATE.mkdir(mode=0o700,exist_ok=True)
    if PRIVATE.is_symlink() or PRIVATE.stat().st_uid!=os.getuid() or PRIVATE.stat().st_dev!=SHELL.parent.stat().st_dev:
        raise RuntimeError("Unsafe private rollback directory")
    with open(PRIVATE/"lock","a+") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        raw=SHELL.read_bytes()
        receipt=PRIVATE/("receipt-"+number+".json")
        backup=PRIVATE/("backup-"+number+".php")
        if action=="install":
            if checksum(raw)!=PRE_SHA:
                if MARK in raw.decode("utf8","replace"):raise RuntimeError("Already installed: refuse duplicate publish")
                raise RuntimeError("PHP source drift; refuse changes")
            s=raw.decode("utf8")
            updated,changed=patch(s)
            if not changed:raise RuntimeError("Already exists")
            new=updated.encode()
            draft=PRIVATE/("candidate-"+number+".php")
            write_new(draft,new)
            php_lint(draft)
            write_new(backup,raw)
            info={"run_id":number,"commit":gitsha,"release_id":RELEASE,"nav_version":NAV_VERSION,"before_sha256":checksum(raw),"after_sha256":checksum(new),"backup":str(backup)}
            write_new(receipt,json.dumps(info,sort_keys=True).encode())
            if checksum(SHELL.read_bytes())!=info["before_sha256"]:raise RuntimeError("Concurrent edit detected")
            os.chmod(draft,stat.S_IMODE(SHELL.stat().st_mode))
            os.replace(draft,SHELL)
            if checksum(SHELL.read_bytes())!=info["after_sha256"]:raise RuntimeError("Post-swap PHP hash mismatch")
            print("NEXTWAVE_NAV_ATOMIC_INSTALL",json.dumps(info,sort_keys=True))
        elif action=="rollback":
            if not receipt.is_file() or receipt.is_symlink() or not backup.is_file() or backup.is_symlink():
                raise RuntimeError("Missing verified rollback receipt")
            info=json.loads(receipt.read_text())
            if info["run_id"]!=number or info["commit"]!=gitsha or info["release_id"]!=RELEASE:
                raise RuntimeError("Rollback provenance mismatch")
            if checksum(raw)!=info["after_sha256"] or checksum(backup.read_bytes())!=info["before_sha256"]:
                raise RuntimeError("Concurrent modification: refusing unsafe rollback")
            temp=PRIVATE/("restore-"+number+".php")
            write_new(temp,backup.read_bytes())
            php_lint(temp)
            os.chmod(temp,stat.S_IMODE(SHELL.stat().st_mode))
            os.replace(temp,SHELL)
            if checksum(SHELL.read_bytes())!=info["before_sha256"]:raise RuntimeError("Rollback failed integrity test")
            print("NEXTWAVE_NAV_EXACT_ROLLBACK_PASS")
        else:raise RuntimeError("Invalid operation")
def selftest():
    fixture="<?php\n// MPW_ARCADE_MAIN_DISCOVERY_20261023_END\n$slug='games';$rendered='<main><h1>Game</h1></main>';\necho $rendered;\n"
    n,c=patch(fixture)
    assert c and n.count("// "+MARK+"_BEGIN")==1
    n2,c2=patch(n)
    assert not c2 and n2==n
    assert n.count('href="/mpw-editorial/nextwave/20261023/orbit-switch/index.html"')==1
    assert n.count('href="/mpw-editorial/nextwave/20261023/frame-budget-lab/index.html"')==1
    for bad in (fixture.replace("echo $rendered;","print $rendered;"),fixture.replace("MPW_ARCADE_MAIN_DISCOVERY_20261023_END","missing")):
        try:patch(bad)
        except RuntimeError:pass
        else:raise AssertionError("Broken source accepted")
    from tempfile import TemporaryDirectory
    with TemporaryDirectory() as t:
        p=Path(t)/"fixture.php";p.write_text(n);php_lint(p)
    print("NEXTWAVE_MAIN_NAV_SELFTEST_PASS")
if __name__=="__main__":
    if sys.argv[1:]==["selftest"]:selftest()
    elif len(sys.argv)==4:run(*sys.argv[1:])
    else:raise SystemExit("selftest | install RUN_ID SHA | rollback RUN_ID SHA")
