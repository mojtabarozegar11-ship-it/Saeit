#!/usr/bin/env python3
"""Exact-hash guarded discovery links for new Field Studio release on two GET pages.
The only modified production file is the previously-owned dynamic shell PHP.
Never edits .htaccess, Django, Passenger, document root or existing game files.
"""
import fcntl,hashlib,json,os,pwd,re,shutil,stat,subprocess,sys
from pathlib import Path
HOME=Path("/home/zomorod2")
SITE=HOME/"mojplaywin.com"
SHELL=SITE/"design-preview-20261017"/"_mpw_dynamic_main_shell_20261019.php"
HTACCESS=SITE/".htaccess"
PRIVATE=HOME/".private_mpw_fieldstudio_main_nav_20261023"
ORIGINAL_SHA="9cc5942a30b48f8300c90511b6a113452bce5ef87172fc14fc225f2397db79ee"
HTACCESS_SHA="6d06dc358b118ca59843941cd79c627eb4792a3584b0d11b4de7ed49b8552b63"
VERSION="MPW-FIELDGUIDES-20261023-01"
NAV="FIELDSTUDIO-MAIN-NAV-20261023-01"
MARK="MPW_FIELDSTUDIO_MAIN_NAV_20261023"
GAME="/mpw-editorial/field-guides/20261023/prism-relay/index.html"
GUIDES="/mpw-editorial/field-guides/20261023/index.html"
PHP_PATCH=r"""
// MPW_FIELDSTUDIO_MAIN_NAV_20261023_BEGIN
// Render only after known owner cards on the two existing GET-only public routes.
if (($slug === 'games' || $slug === 'products') &&
    strpos($rendered,'id="mpw-fieldstudio-discovery-20261023"') === false &&
    preg_match_all('~</main\s*>~i',$rendered) === 1) {
    $fieldStudioNeedle = ($slug === 'games')
        ? 'id="mpw-nextwave-main-discovery-20261023"'
        : 'id="mpw-assetlab-main-discovery-20261023"';
    $fieldStudioCue = ($slug === 'games') ? 'First Realm' : 'Digital Products';
    if (strpos($rendered,$fieldStudioNeedle)!==false &&
        strpos($rendered,$fieldStudioCue)!==false) {
        if ($slug === 'games') {
            $fieldStudioCard=<<<'FIELD_STUDIO_GAME'
<section id="mpw-fieldstudio-discovery-20261023" data-fieldstudio-release="MPW-FIELDGUIDES-20261023-01" data-navigation-version="FIELDSTUDIO-MAIN-NAV-20261023-01" aria-label="New Prism Relay puzzle game" style="margin:22px 0;padding:20px;border-radius:18px;border:1px solid #3d837f;background:#0b2534;color:#e4faff">
  <h2 style="margin-top:0;color:#ffe0a6">New game: Prism Relay — 150 stages</h2>
  <p>Rotate mirrors to guide a golden laser through 150 solvable puzzles. Mobile and keyboard play, undo, hints and saved progress.</p>
  <a href="/mpw-editorial/field-guides/20261023/prism-relay/index.html" style="display:block;padding:14px;border:1px solid #68a79e;border-radius:13px;color:#9bfce2;text-decoration:none;font-weight:800">
    <svg aria-hidden="true" viewBox="0 0 320 100" width="320" height="100" style="max-width:100%;width:100%;height:auto;border-radius:9px;background:#061a2e" xmlns="http://www.w3.org/2000/svg">
      <path d="M20 52H100V20H210V76H300" stroke="#f8c96e" stroke-width="6" fill="none" stroke-linejoin="round"/>
      <rect x="90" y="12" width="20" height="20" rx="3" fill="#6fe3d7" transform="rotate(-45 100 22)"/>
      <rect x="200" y="66" width="20" height="20" rx="3" fill="#6fe3d7" transform="rotate(45 210 76)"/>
      <circle cx="21" cy="52" r="12" fill="#ffd39b"/><circle cx="300" cy="76" r="13" fill="#59e4ad"/>
    </svg>
    Play Prism Relay free →
  </a>
  <p style="margin-bottom:0"><a href="/mpw-editorial/field-guides/20261023/index.html" style="color:#ffe0a6">Explore 50 new practical game-development guides →</a></p>
</section>
FIELD_STUDIO_GAME;
        } else {
            $fieldStudioCard=<<<'FIELD_STUDIO_GUIDES'
<section id="mpw-fieldstudio-discovery-20261023" data-fieldstudio-release="MPW-FIELDGUIDES-20261023-01" data-navigation-version="FIELDSTUDIO-MAIN-NAV-20261023-01" aria-label="New MojPlayWin game production guides" style="margin:22px 0;padding:20px;border-radius:18px;border:1px solid #3d837f;background:#0b2534;color:#e4faff">
  <h2 style="margin-top:0;color:#ffe0a6">New: 50 practical game-production guides</h2>
  <p>Read independent, source-linked implementation notes covering performance, responsive assets, touch controls, accessibility and browser security. Includes a new free laser puzzle game.</p>
  <a href="/mpw-editorial/field-guides/20261023/index.html" style="display:block;padding:14px;border:1px solid #68a79e;border-radius:13px;color:#9bfce2;text-decoration:none;font-weight:800">
    <svg aria-hidden="true" viewBox="0 0 320 100" width="320" height="100" style="max-width:100%;width:100%;height:auto;border-radius:9px;background:#061a2e" xmlns="http://www.w3.org/2000/svg">
      <rect x="50" y="18" width="70" height="64" rx="7" stroke="#81dacb" stroke-width="3" fill="#133950"/>
      <rect x="125" y="25" width="70" height="57" rx="7" stroke="#ffd39b" stroke-width="3" fill="#1b3451"/>
      <rect x="200" y="32" width="70" height="50" rx="7" stroke="#81dacb" stroke-width="3" fill="#133950"/>
      <path d="M62 41H107M62 51H102M62 61H98M137 45H180M137 55H175M211 53H258" stroke="#a8daef" stroke-width="3" stroke-linecap="round"/>
    </svg>
    Browse 50 original field guides →
  </a>
  <p style="margin-bottom:0"><a href="/mpw-editorial/field-guides/20261023/prism-relay/index.html" style="color:#ffe0a6">Play Prism Relay free →</a></p>
</section>
FIELD_STUDIO_GUIDES;
        }
        $fieldStudioCount=0;
        $fieldStudioOutput=preg_replace_callback('~</main\s*>~i',
            static function(array $match) use ($fieldStudioCard):string {
                return "\n".$fieldStudioCard."\n".$match[0];
            },$rendered,1,$fieldStudioCount);
        if ($fieldStudioCount===1 && is_string($fieldStudioOutput) &&
            substr_count($fieldStudioOutput,'id="mpw-fieldstudio-discovery-20261023"')===1) {
            $rendered=$fieldStudioOutput;
        }
    }
}
// MPW_FIELDSTUDIO_MAIN_NAV_20261023_END
"""
def sha(b):return hashlib.sha256(b).hexdigest()
def patch(s):
    if MARK in s:
        if s.count("// "+MARK+"_BEGIN")!=1 or s.count("// "+MARK+"_END")!=1:
            raise RuntimeError("Untrusted existing marker")
        return s,False
    anchor="\necho $rendered;"
    if s.count(anchor)!=1 or not s.rstrip().endswith("echo $rendered;"):
        raise RuntimeError("Unknown PHP output anchor")
    for marker in ("MPW_ARCADE_MAIN_DISCOVERY_20261023_END","mpw-nextwave-main-discovery-20261023","MPW_ASSETLAB_MAIN_NAV_20261023_END"):
        if marker not in s:raise RuntimeError("Existing owner card absent: "+marker)
    out=s.replace(anchor,"\n"+PHP_PATCH.strip("\n")+"\n"+anchor,1)
    if out.count("// "+MARK+"_BEGIN")!=1:raise RuntimeError("Injection duplication")
    return out,True
def gate():
    if pwd.getpwuid(os.getuid()).pw_name!="zomorod2":raise RuntimeError("Wrong cPanel user")
    for p in (SITE,SHELL.parent,SHELL,HTACCESS):
        if not p.exists() or p.is_symlink() or p.stat().st_uid!=os.getuid():raise RuntimeError("Owner validation failed")
    if sha(HTACCESS.read_bytes())!=HTACCESS_SHA:raise RuntimeError("Routing digest mismatch")
    root=SITE/"mpw-editorial"/"field-guides"/"20261023"
    manifest=root/"release.json"
    if not manifest.is_file() or manifest.is_symlink():raise RuntimeError("Missing public release")
    j=json.loads(manifest.read_text())
    if j.get("release_id")!=VERSION or j.get("guide_count")!=50 or j.get("stage_count")!=150:
        raise RuntimeError("Untrusted public release")
    for p in (root/"prism-relay/index.html",root/"index.html"):
        if not p.is_file() or p.is_symlink() or sha(p.read_bytes())!=j["files_sha256"][p.relative_to(root).as_posix()]:
            raise RuntimeError("Public release checksum mismatch")
def lint(path):
    cmd=shutil.which("php")
    if not cmd:
        for v in ("83","82","81"):
            p="/opt/cpanel/ea-php"+v+"/root/usr/bin/php"
            if Path(p).is_file():cmd=p;break
    if not cmd:raise RuntimeError("No PHP linter")
    r=subprocess.run([cmd,"-l",str(path)],capture_output=True,text=True,timeout=25)
    if r.returncode or "No syntax errors detected" not in (r.stdout+r.stderr):raise RuntimeError("PHP lint failed "+r.stdout+r.stderr)
    print("FIELDSTUDIO_PHP_SYNTAX_PASS")
def atomic(path,bytes_data,original_mode):
    temp=PRIVATE/("ready-"+str(os.getpid())+".php")
    if temp.exists() or temp.is_symlink():raise RuntimeError("Temp collision")
    with open(temp,"xb") as f:f.write(bytes_data);f.flush();os.fsync(f.fileno())
    temp.chmod(original_mode)
    return temp
def operate(mode,run,commit):
    if not re.fullmatch(r"[0-9]{8,20}",run) or not re.fullmatch(r"[a-f0-9]{40}",commit):raise RuntimeError("Bad identity")
    gate()
    PRIVATE.mkdir(mode=0o700,exist_ok=True)
    if PRIVATE.is_symlink() or PRIVATE.stat().st_uid!=os.getuid() or PRIVATE.stat().st_dev!=SHELL.stat().st_dev:
        raise RuntimeError("Private area unsafe")
    with open(PRIVATE/"lock","a+") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        old=SHELL.read_bytes()
        receipt=PRIVATE/("receipt-"+run+".json")
        backup=PRIVATE/("original-"+run+".php")
        if mode=="install":
            if sha(old)!=ORIGINAL_SHA:raise RuntimeError("Source SHA changed: fail closed")
            if receipt.exists() or backup.exists():raise RuntimeError("Run conflict")
            new,changed=patch(old.decode("utf8"))
            if not changed:raise RuntimeError("Existing card found")
            candidate=atomic(SHELL,new.encode("utf8"),0o600)
            lint(candidate)
            with open(backup,"xb") as f:f.write(old);f.flush();os.fsync(f.fileno())
            backup.chmod(0o600)
            details={"run":run,"commit":commit,"old_sha":sha(old),"new_sha":sha(new.encode("utf8")),"backup":backup.name,"version":NAV}
            with open(receipt,"x") as f:json.dump(details,f,sort_keys=True);f.flush();os.fsync(f.fileno())
            receipt.chmod(0o600)
            if sha(SHELL.read_bytes())!=details["old_sha"]:raise RuntimeError("Concurrent change")
            candidate.chmod(stat.S_IMODE(SHELL.stat().st_mode))
            os.replace(candidate,SHELL)
            if sha(SHELL.read_bytes())!=details["new_sha"]:raise RuntimeError("Post-install hash mismatch")
            print("FIELDSTUDIO_MAIN_NAV_DEPLOYED",json.dumps(details,sort_keys=True))
        elif mode=="rollback":
            if not receipt.is_file() or not backup.is_file() or receipt.is_symlink() or backup.is_symlink():
                print("FIELDSTUDIO_NO_RECEIPT_NO_ROLLBACK");return
            d=json.loads(receipt.read_text())
            if d["run"]!=run or d["commit"]!=commit or d["version"]!=NAV:raise RuntimeError("Wrong rollback identity")
            old_bytes=backup.read_bytes()
            if sha(SHELL.read_bytes())!=d["new_sha"] or sha(old_bytes)!=d["old_sha"]:raise RuntimeError("Concurrent edit; rollback refused")
            ready=atomic(SHELL,old_bytes,stat.S_IMODE(SHELL.stat().st_mode))
            lint(ready);os.replace(ready,SHELL)
            if sha(SHELL.read_bytes())!=d["old_sha"]:raise RuntimeError("Rollback SHA mismatch")
            print("FIELDSTUDIO_NAV_EXACT_ROLLBACK_PASS",run)
        else:raise RuntimeError("Unknown operation")
def selftest():
    fixture="<?php\n// MPW_ARCADE_MAIN_DISCOVERY_20261023_END\n// mpw-nextwave-main-discovery-20261023\n// MPW_ASSETLAB_MAIN_NAV_20261023_END\n$slug='games';\n$rendered='<main><h1>Games</h1></main>';\necho $rendered;\n"
    new,yes=patch(fixture)
    assert yes and new.count("// "+MARK+"_BEGIN")==1
    second,no=patch(new)
    assert not no and second==new
    for mutation in (fixture.replace("echo $rendered;","echo $other;"),fixture.replace("// MPW_ASSETLAB_MAIN_NAV_20261023_END","")):
        try:patch(mutation)
        except RuntimeError:pass
        else:raise AssertionError("Unsafe source accepted")
    from tempfile import TemporaryDirectory
    with TemporaryDirectory() as d:
        p=Path(d)/"nav.php";p.write_text(new);lint(p)
    print("FIELDSTUDIO_MAIN_NAV_IDEMPOTENCY_AND_PHP_QA_PASS")
if __name__=="__main__":
    if sys.argv[1:]==["selftest"]:selftest()
    elif len(sys.argv)==4:operate(*sys.argv[1:])
    else:raise SystemExit("selftest | install RUN_ID SHA | rollback RUN_ID SHA")
