#!/usr/bin/env python3
"""Append one reversible team section to the isolated MojPlayWin /about/ static file only."""
import hashlib,json,os,re,stat,sys,tempfile
from pathlib import Path

ROOT=Path("/home/zomorod2/mojplaywin.com")
PAGE=ROOT/"design-preview-20261017/complete-about-20261018.html"
HTACCESS=ROOT/".htaccess"
MARKER="mpw-meet-team-20261018"
OLD_MARKERS=("Original by Default","MPW_ABOUT_RESEARCH_80_20_V1","SPECIALISM 28",
             "COMPLEMENTARY SPECIALISM 30","Mojtaba Roozegar")

def hash_bytes(raw):return hashlib.sha256(raw).hexdigest()
def check(ok,description):
    if not ok:raise RuntimeError(description)
def safeid(runid):
    check(re.fullmatch(r"[0-9]{9,20}",runid),"Invalid run ID")
    return runid
def paths(runid):
    rid=safeid(runid)
    return (ROOT.parent/f".mpw-team-stage-{rid}.html",
            ROOT.parent/f".mpw-team-backup-{rid}.html",
            ROOT.parent/f".mpw-team-manifest-{rid}.json")
def atom(target,data,mode):
    check(not target.is_symlink(),"Target symlink")
    fd,temp=tempfile.mkstemp(prefix=".mpw-team-",dir=target.parent)
    try:
        os.fchmod(fd,mode)
        with os.fdopen(fd,"wb") as f:
            f.write(data);f.flush();os.fsync(f.fileno())
        os.replace(temp,target)
    finally:
        if os.path.exists(temp):os.unlink(temp)

def guard():
    check(ROOT.is_dir() and not ROOT.is_symlink(),"Unknown document root")
    check(PAGE.is_file() and not PAGE.is_symlink(),"Unknown About file")
    check(HTACCESS.is_file() and not HTACCESS.is_symlink(),"Unknown About routing")
    rules=HTACCESS.read_text(encoding="utf-8",errors="replace")
    for phrase in ("MPW_EXACT_ABOUT_80_20_20261018",
                   "RewriteCond %{REQUEST_URI} ^/about/$",
                   "RewriteRule ^about/$ /design-preview-20261017/complete-about-20261018.html"):
        check(phrase in rules,"Exact About route has changed: "+phrase)
    raw=PAGE.read_bytes()
    check(50000<=len(raw)<=1500000,"Unexpected current About length")
    old=raw.decode("utf-8")
    check(MARKER not in old,"Team already present; refuse duplicate")
    for marker in OLD_MARKERS:check(marker in old,"Required original content absent: "+marker)
    check(len(re.findall(r"<main\b",old,re.I))==1 and
          len(re.findall(r"</main\s*>",old,re.I))==1,"Main landmark count changed")
    return raw,old

def compose(old,snippet):
    check(22000<=len(snippet.encode("utf-8"))<=45000,"Team payload size differs")
    check(snippet.count("data:image/avif;base64,")==1,"Team image missing or duplicated")
    check(snippet.count('class="mpw-team-card"')==10,"Team card count mismatch")
    check(snippet.count('<section id="mpw-meet-team-20261018"')==1,"Section marker mismatch")
    check(not re.search(r"<script\b|<iframe\b|{[%{]",snippet,re.I),"Unsafe team HTML")
    for name in ("Sophia","Isabella","Olivia","Camila","Valentina","Emma",
                 "Charlotte","Amelia","Luca","Noah"):
        check(f"<h3>{name}</h3>" in snippet,"Missing profile "+name)
    matches=list(re.finditer(r"</main\s*>",old,re.I))
    check(len(matches)==1,"Missing unique main end")
    addon="\n<!-- MPW_TEAM_ADDON_V1 -->\n"+snippet+"\n"
    pos=matches[0].start()
    result=old[:pos]+addon+old[pos:]
    check(result.replace(addon,"",1)==old,"Insertion not reversible")
    check(len(result.encode("utf-8"))<1550000,"Expanded document too large")
    check(len(re.findall(r"<h1\b",old,re.I))==len(re.findall(r"<h1\b",result,re.I)),
          "Existing H1 count altered")
    return result.encode("utf-8")

def install(runid,expected):
    stage,backup,manifest=paths(runid)
    check(re.fullmatch(r"[a-f0-9]{64}",expected),"Invalid staged hash")
    check(stage.is_file() and not stage.is_symlink(),"Missing private staged payload")
    data=stage.read_bytes()
    check(hash_bytes(data)==expected,"Payload digest mismatch")
    previous,old=guard()
    check(not backup.exists() and not backup.is_symlink(),"Backup already exists")
    check(not manifest.exists() and not manifest.is_symlink(),"Manifest already exists")
    updated=compose(old,data.decode("utf-8"))
    with open(backup,"xb") as f:
        os.chmod(backup,0o600)
        f.write(previous);f.flush();os.fsync(f.fileno())
    record={"runid":runid,"before":hash_bytes(previous),"after":hash_bytes(updated),
            "payload_sha":expected,"page":str(PAGE)}
    with open(manifest,"x",encoding="utf-8") as f:
        os.chmod(manifest,0o600)
        json.dump(record,f);f.flush();os.fsync(f.fileno())
    check(hash_bytes(PAGE.read_bytes())==record["before"],"Concurrent edit; stop")
    mode=stat.S_IMODE(PAGE.stat().st_mode)
    try:
        atom(PAGE,updated,mode)
        check(hash_bytes(PAGE.read_bytes())==record["after"],"Post-write mismatch")
    except BaseException:
        if PAGE.is_file() and hash_bytes(PAGE.read_bytes())==record["after"]:
            atom(PAGE,previous,mode)
        raise
    stage.unlink()
    print(json.dumps({"result":"TEAM_PUBLISHED","sha_before":record["before"],
                      "sha_after":record["after"],"profiles":10,
                      "passenger_restarted":False,"other_files_modified":False}))

def rollback(runid):
    _,backup,manifest=paths(runid)
    check(backup.is_file() and not backup.is_symlink(),"Recovery backup missing")
    check(manifest.is_file() and not manifest.is_symlink(),"Recovery manifest missing")
    record=json.loads(manifest.read_text())
    previous=backup.read_bytes()
    check(hash_bytes(previous)==record["before"],"Backup digest mismatch")
    check(PAGE.is_file() and not PAGE.is_symlink(),"Unknown rollback target")
    check(hash_bytes(PAGE.read_bytes())==record["after"],"Concurrent change; refuse rollback")
    atom(PAGE,previous,stat.S_IMODE(PAGE.stat().st_mode))
    check(hash_bytes(PAGE.read_bytes())==record["before"],"Rollback digest mismatch")
    print(json.dumps({"result":"TEAM_ROLLED_BACK","sha":record["before"]}))

def status(runid):
    _,backup,manifest=paths(runid)
    record=json.loads(manifest.read_text()) if manifest.is_file() else {}
    digest=hash_bytes(PAGE.read_bytes()) if PAGE.is_file() and not PAGE.is_symlink() else ""
    print(json.dumps({"result":"TEAM_STATUS","installed":digest==record.get("after"),
                      "backup_exists":backup.is_file(),"page_sha":digest}))

if __name__=="__main__":
    check(len(sys.argv)>=3,"Usage: install|rollback|status RUNID [SHA]")
    action,rid=sys.argv[1:3]
    if action=="install" and len(sys.argv)==4:install(rid,sys.argv[3])
    elif action=="rollback" and len(sys.argv)==3:rollback(rid)
    elif action=="status" and len(sys.argv)==3:status(rid)
    else:raise RuntimeError("Invalid command")
