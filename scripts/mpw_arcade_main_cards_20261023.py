#!/usr/bin/env python3
"""Guarded and reversible Arcade Lab discovery on exactly two MojPlayWin GET pages.

Changes only the owned PHP transformer after its GET/host checks, not rewrite
rules, shared Django templates, Passenger, docroot, or other child sites.
"""
import fcntl
import hashlib
import json
import os
import pwd
import re
import shutil
import stat
import subprocess
import sys
from pathlib import Path

HOME = Path("/home/zomorod2")
SITE = HOME / "mojplaywin.com"
SHELL = SITE / "design-preview-20261017" / "_mpw_dynamic_main_shell_20261019.php"
HTACCESS = SITE / ".htaccess"
PRIVATE = HOME / ".private_mpw_arcade_main_cards_20261023"
BASE_SHA256 = "e2d848c19be0c716e8ca4b04b1466aa5b4d4765c3921ab7a34d9f56a76a62480"
HTACCESS_SHA256 = "6d06dc358b118ca59843941cd79c627eb4792a3584b0d11b4de7ed49b8552b63"
ARCADE_SHA = "04ba43522db4af1762c99a5e60eb280cba1dd8b5"
MARK = "MPW_ARCADE_MAIN_DISCOVERY_20261023"
ROUTE_VERSION = "mpw-arcade-navigation-v1-20261023"

PHP_PATCH = r"""
// MPW_ARCADE_MAIN_DISCOVERY_20261023_BEGIN
// Only existing GET-only, MojPlayWin-host-only dynamic shell routes are eligible.
// Unrecognized source HTML returns without modification; no redirects or writes.
if (($slug === 'games' || $slug === 'products') &&
    strpos($rendered, 'id="mpw-arcade-main-discovery-20261023"') === false) {
    $arcadeCue = $slug === 'games' ? 'First Realm' : 'Digital Products';
    if (strpos($rendered, $arcadeCue) !== false &&
        preg_match_all('~<main\b[^>]*>~i', $rendered) === 1 &&
        preg_match_all('~<h1\b[^>]*>~i', $rendered) === 1 &&
        preg_match_all('~</main\s*>~i', $rendered) === 1) {
        if ($slug === 'games') {
            $arcadeCard = <<<'MPW_ARCADE_GAME'
<section id="mpw-arcade-main-discovery-20261023" data-arcade-sha="04ba43522db4af1762c99a5e60eb280cba1dd8b5" data-navigation-version="mpw-arcade-navigation-v1-20261023" aria-label="Arcade Lab — Circuit Courier" style="margin:22px 0;padding:clamp(15px,3vw,27px);border:1px solid #718598;border-radius:18px;background:#0d1b2c;color:#f2f7ff">
  <h2 style="margin:0 0 9px;color:#ffe3aa">Arcade Lab — Circuit Courier</h2>
  <p>Play 60 original circuit puzzles directly in your browser. Explore the related design tools and 50 research-oriented guides.</p>
  <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,220px),1fr));gap:14px">
    <a href="/mpw-editorial/arcade-lab/20261022/circuit-courier/index.html" style="display:block;padding:12px;border:1px solid #52708c;border-radius:12px;color:#fff0d4;background:#14283e"><img src="/mpw-editorial/arcade-lab/20261022/assets/circuit-courier.webp" alt="Circuit Courier, a browser puzzle game about connecting an electrical grid" loading="lazy" decoding="async" width="290" height="160" style="display:block;max-width:100%;width:100%;height:auto;border-radius:8px"><strong style="display:block;margin-top:8px">Play Circuit Courier →</strong></a>
  </div>
  <p><a style="color:#ffe3aa" href="/mpw-editorial/arcade-lab/20261022/index.html">See all Arcade Lab releases →</a> · <a style="color:#ffe3aa" href="/mpw-editorial/arcade-lab/20261022/guides/index.html">Read 50 guides →</a></p>
</section>
MPW_ARCADE_GAME;
        } else {
            $arcadeCard = <<<'MPW_ARCADE_PRODUCTS'
<section id="mpw-arcade-main-discovery-20261023" data-arcade-sha="04ba43522db4af1762c99a5e60eb280cba1dd8b5" data-navigation-version="mpw-arcade-navigation-v1-20261023" aria-label="Arcade Lab — interactive digital tools" style="margin:22px 0;padding:clamp(15px,3vw,27px);border:1px solid #718598;border-radius:18px;background:#0d1b2c;color:#f2f7ff">
  <h2 style="margin:0 0 9px;color:#ffe3aa">Arcade Lab — interactive tools</h2>
  <p>Try two free, working game-development utilities and browse their supporting research-oriented guides.</p>
  <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,220px),1fr));gap:14px">
    <a href="/mpw-editorial/arcade-lab/20261022/economy-simulator/index.html" style="display:block;padding:12px;border:1px solid #52708c;border-radius:12px;color:#fff0d4;background:#14283e"><img src="/mpw-editorial/arcade-lab/20261022/assets/economy-simulator.webp" alt="Game Economy Simulator for exploring resource and reward balances" loading="lazy" decoding="async" width="290" height="160" style="display:block;max-width:100%;width:100%;height:auto;border-radius:8px"><strong style="display:block;margin-top:8px">Game Economy Simulator →</strong></a>
    <a href="/mpw-editorial/arcade-lab/20261022/qa-matrix/index.html" style="display:block;padding:12px;border:1px solid #52708c;border-radius:12px;color:#fff0d4;background:#14283e"><img src="/mpw-editorial/arcade-lab/20261022/assets/qa-matrix.webp" alt="Game QA Matrix for checking browser game behavior and quality" loading="lazy" decoding="async" width="290" height="160" style="display:block;max-width:100%;width:100%;height:auto;border-radius:8px"><strong style="display:block;margin-top:8px">Game QA Matrix →</strong></a>
  </div>
  <p><a style="color:#ffe3aa" href="/mpw-editorial/arcade-lab/20261022/index.html">See all Arcade Lab releases →</a> · <a style="color:#ffe3aa" href="/mpw-editorial/arcade-lab/20261022/guides/index.html">Read 50 guides →</a></p>
</section>
MPW_ARCADE_PRODUCTS;
        }
        $arcadeCount = 0;
        $arcadeOutput = preg_replace_callback(
            '~(<main\b[^>]*>[\s\S]*?</h1\s*>)~i',
            static function (array $m) use ($arcadeCard): string {
                return $m[1] . "\n" . $arcadeCard;
            },
            $rendered, 1, $arcadeCount
        );
        if ($arcadeCount === 1 && is_string($arcadeOutput) &&
            substr_count($arcadeOutput, 'id="mpw-arcade-main-discovery-20261023"') === 1) {
            $rendered = $arcadeOutput;
        }
    }
}
// MPW_ARCADE_MAIN_DISCOVERY_20261023_END
"""

def digest(data):
    return hashlib.sha256(data).hexdigest()

def patch(source):
    if MARK in source:
        if source.count("// " + MARK + "_BEGIN") != 1 or source.count("// " + MARK + "_END") != 1:
            raise RuntimeError("Unexpected pre-existing card marker")
        return source, False
    anchor = "\necho $rendered;"
    if source.count(anchor) != 1 or not source.rstrip().endswith("echo $rendered;"):
        raise RuntimeError("Expected PHP final rendering anchor absent")
    if "// ATELIER_879_STOREFRONT_ONLY_20261022_END" not in source:
        raise RuntimeError("Unrecognized existing production shell")
    return source.replace(anchor, "\n" + PHP_PATCH.strip("\n") + "\n" + anchor, 1), True

def validate_environment():
    if pwd.getpwuid(os.getuid()).pw_name != "zomorod2":
        raise RuntimeError("Refusing wrong account")
    for p in (SITE, SHELL.parent, SHELL, HTACCESS):
        if p.is_symlink() or not p.exists():
            raise RuntimeError("Refusing symlink or missing path")
        if p.stat().st_uid != os.getuid():
            raise RuntimeError("Unexpected owner: " + str(p))
    if SHELL.stat().st_size > 70000 or not SHELL.is_file():
        raise RuntimeError("Unexpected PHP file")
    if digest(HTACCESS.read_bytes()) != HTACCESS_SHA256:
        raise RuntimeError("Protected routing rules have changed")
    manifest = SITE / "mpw-editorial/arcade-lab/20261022/release.json"
    if manifest.is_symlink() or not manifest.is_file():
        raise RuntimeError("Missing release manifest")
    if json.loads(manifest.read_text()).get("git_sha") != ARCADE_SHA:
        raise RuntimeError("Arcade Lab release version mismatch")
    base = manifest.parent
    for slug in ("economy-simulator", "qa-matrix", "circuit-courier"):
        html = base / slug / "index.html"
        asset = base / "assets" / (slug + ".webp")
        if any(x.is_symlink() or not x.is_file() or not 100 < x.stat().st_size < 500000 for x in (html,asset)):
            raise RuntimeError("Missing/unsafe owned Arcade Lab file: "+slug)
        b=asset.read_bytes()
        if b[:4] != b"RIFF" or b[8:12] != b"WEBP":
            raise RuntimeError("Invalid existing WebP asset")
    guide = base/"guides/index.html"
    if guide.is_symlink() or not guide.is_file():
        raise RuntimeError("Missing public guides index")

def write_once(path, data, mode=0o600):
    if path.exists() or path.is_symlink():
        raise RuntimeError("Collision: " + str(path))
    with open(path, "xb") as f:
        f.write(data); f.flush(); os.fsync(f.fileno())
    path.chmod(mode)

def php_lint(path):
    binary = shutil.which("php")
    if not binary:
        for p in ("/opt/cpanel/ea-php83/root/usr/bin/php", "/opt/cpanel/ea-php82/root/usr/bin/php", "/opt/cpanel/ea-php81/root/usr/bin/php"):
            if Path(p).is_file():
                binary=p;break
    if not binary:
        raise RuntimeError("No PHP CLI for syntax gate")
    p = subprocess.run([binary, "-l", str(path)], capture_output=True, text=True, timeout=25)
    if p.returncode != 0 or "No syntax errors detected" not in (p.stdout+p.stderr):
        raise RuntimeError("Candidate failed PHP lint: "+(p.stdout+p.stderr)[:400])
    print("PHP_LINT_PASS",binary)

def operate(mode, run_id, commit):
    if not re.fullmatch(r"[0-9]{8,20}", run_id) or not re.fullmatch(r"[a-f0-9]{40}",commit):
        raise RuntimeError("Invalid signed run identity")
    validate_environment()
    PRIVATE.mkdir(mode=0o700,exist_ok=True)
    if PRIVATE.is_symlink() or PRIVATE.stat().st_uid != os.getuid():
        raise RuntimeError("Unsafe private backup location")
    os.chmod(PRIVATE,0o700)
    if PRIVATE.stat().st_dev != SHELL.parent.stat().st_dev:
        raise RuntimeError("Atomic rename not possible")
    lockfile = PRIVATE / "exclusive.lock"
    with open(lockfile,"a+") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        source=SHELL.read_bytes()
        original_sha=digest(source)
        receipt=PRIVATE/("receipt-"+run_id+".json")
        backup=PRIVATE/("original-"+run_id+".php")
        if mode=="install":
            if receipt.exists() or backup.exists():
                raise RuntimeError("Run id already used")
            original=source.decode("utf-8")
            desired,changed=patch(original)
            if not changed:
                print("EXISTING_MARKER_NO_DUPLICATION");return
            if original_sha!=BASE_SHA256:
                raise RuntimeError("PHP production hash mismatch - no mutation")
            candidate=PRIVATE/("candidate-"+run_id+".php")
            new=desired.encode("utf-8")
            write_once(candidate,new,0o600)
            php_lint(candidate)
            write_once(backup,source,0o600)
            info={"run_id":run_id,"commit":commit,"source_sha256":original_sha,"deployed_sha256":digest(new),"arcade_sha":ARCADE_SHA,"route_version":ROUTE_VERSION,"scope":["/games/","/products/"],"backup":backup.name}
            write_once(receipt,json.dumps(info,sort_keys=True).encode(),0o600)
            if digest(SHELL.read_bytes())!=original_sha:
                raise RuntimeError("Concurrent modification before atomic swap")
            candidate.chmod(stat.S_IMODE(SHELL.stat().st_mode))
            os.replace(candidate,SHELL)
            if digest(SHELL.read_bytes())!=info["deployed_sha256"]:
                if digest(SHELL.read_bytes())==original_sha:
                    raise RuntimeError("No deployment observed")
                raise RuntimeError("Post-swap file hash mismatch: intervention required")
            print("MAIN_CARD_GUARDED_PHP_DEPLOY",json.dumps(info,sort_keys=True))
        elif mode=="rollback":
            if not receipt.is_file() or receipt.is_symlink() or not backup.is_file() or backup.is_symlink():
                raise RuntimeError("No trusted receipt and backup")
            info=json.loads(receipt.read_text())
            if (info.get("run_id"),info.get("commit"),info.get("arcade_sha"))!=(run_id,commit,ARCADE_SHA):
                raise RuntimeError("Rollback identity mismatch")
            old=backup.read_bytes()
            if digest(old)!=info["source_sha256"] or digest(SHELL.read_bytes())!=info["deployed_sha256"]:
                raise RuntimeError("Concurrent change - refuse rollback")
            temp=PRIVATE/("rollback-"+run_id+".php")
            write_once(temp,old,0o600)
            php_lint(temp)
            temp.chmod(stat.S_IMODE(SHELL.stat().st_mode))
            os.replace(temp,SHELL)
            if digest(SHELL.read_bytes())!=info["source_sha256"]:
                raise RuntimeError("Rollback verification failed")
            print("MAIN_CARD_EXACT_ROLLBACK_PASS",json.dumps({"run_id":run_id,"sha256":digest(SHELL.read_bytes())}))
        else:raise RuntimeError("Unrecognized operation")

def selftest():
    example="<?php\n// ATELIER_879_STOREFRONT_ONLY_20261022_END\n$slug='games';\n$rendered='<main><h1>Games</h1></main>';\necho $rendered;\n"
    patched,changed=patch(example)
    assert changed and patched.count("// "+MARK+"_BEGIN")==1 and patched.endswith("echo $rendered;\n")
    again,changed=patch(patched)
    assert not changed and again==patched
    for bad in (example.replace("echo $rendered;","print $rendered;"),example.replace("// ATELIER_879_STOREFRONT_ONLY_20261022_END","")):
        try:patch(bad)
        except RuntimeError:pass
        else:raise AssertionError("Unexpectedly accepted malformed source")
    from tempfile import TemporaryDirectory
    with TemporaryDirectory() as directory:
        path=Path(directory)/"fixture.php"
        path.write_text(patched)
        php_lint(path)
    print("MAIN_CARD_UNIT_IDEMPOTENCY_AND_PHP_LINT_PASS")

if __name__=="__main__":
    if sys.argv[1:]==["selftest"]:
        selftest()
    elif len(sys.argv)==4:
        operate(sys.argv[1],sys.argv[2],sys.argv[3])
    else:
        raise SystemExit("selftest | install RUN_ID SHA | rollback RUN_ID SHA")
