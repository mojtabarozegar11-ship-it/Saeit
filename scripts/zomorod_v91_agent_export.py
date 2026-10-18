"""Controlled V91 source export: read-only Python code + exact integrity manifest.

Run on cPanel: python3 - --stream < this_file.py
No V91 files are modified. No secrets, media, SQLite, or symlinks are copied.
"""
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
import sys
import tarfile

ROOT=Path("/home/zomorod2/saeit_v91")
SITE=ROOT/"zomorodmelal"
LIMIT_TOTAL=30*1024*1024
LIMIT_FILE=5*1024*1024
DENY=re.compile(r"(?i)(?:^\.|secret|password|credential|token|\.pem$|\.key$|^id_rsa|\.env|\.sqlite|\.db$|\.log$|wallet|__pycache__|node_modules|\.venv)")
ALLOWED_SUFFIX={".py",".md",".json",".toml",".txt",".yaml",".yml",".ini",".cfg"}
SKIP_DIRS={"__pycache__", ".git", ".venv", "venv", ".cache", "node_modules"}
TEST_PATTERN=re.compile(r"(?i)(agent|master|singleflight|phase17|site_master)")
DOC_PATTERN=re.compile(r"(?i)(agent|master|gen64|singleflight)")
FILES=[]

def collect(base, predicate):
    if not base.is_dir() or base.is_symlink():
        return
    for path,dirs,files in os.walk(base,followlinks=False):
        dirs[:]=[d for d in dirs if d not in SKIP_DIRS and not DENY.search(d)
                 and not (Path(path)/d).is_symlink()]
        for name in files:
            if DENY.search(name):
                continue
            p=Path(path)/name
            if p.suffix.lower() not in ALLOWED_SUFFIX or not predicate(p):
                continue
            if any(part.startswith(".") for part in p.relative_to(ROOT).parts):
                continue
            s=p.lstat()
            if not stat.S_ISREG(s.st_mode):
                continue
            if s.st_size > LIMIT_FILE:
                raise RuntimeError("Source file exceeds safety threshold")
            FILES.append(p)

collect(SITE/"site_master", lambda p: True)
collect(SITE/"portal", lambda p: p.suffix==".py")
collect(SITE/"tests_offline",lambda p: bool(TEST_PATTERN.search(p.name)))
collect(SITE/"docs",lambda p: bool(DOC_PATTERN.search(p.name)))
for p in (SITE/"requirements.txt",SITE/"manage.py",ROOT/"RELEASE_CHECKLIST_V91_FA.md",
          ROOT/"V91_EXECUTION_AND_REMAINING_FA.md"):
    if p.is_file() and not p.is_symlink() and p.stat().st_size < LIMIT_FILE:
        FILES.append(p)
FILES=sorted(set(FILES),key=lambda x:str(x))
assert len(FILES)>40, "Insufficient V91 agent files; refusing incomplete export"
assert any(str(p).endswith("portal/agent_engine.py") for p in FILES)
assert any(str(p).endswith("commands/run_site_master.py") for p in FILES)
assert any(str(p).endswith("commands/run_site_agents.py") for p in FILES)
assert any("site_master/vendor/master_gen64" in str(p) for p in FILES)
assert sum(p.stat().st_size for p in FILES)<LIMIT_TOTAL
manifest={"source":"saeit_v91/zomorodmelal", "purpose":"Preserved V91 master/agents only",
          "created_utc_date":"2026-10-18","file_count":len(FILES),"files":[]}
mode="--stream" if "--stream" in sys.argv else "--manifest"
for p in FILES:
    rel=str(p.relative_to(ROOT))
    with p.open("rb") as f:
        buf=f.read()
    manifest["files"].append({"path":rel,"bytes":len(buf),"sha256":hashlib.sha256(buf).hexdigest()})
if mode=="--manifest":
    print(json.dumps({"file_count":len(FILES),"raw_bytes":sum(x["bytes"] for x in manifest["files"]),
                      "site_master_count":sum("/site_master/" in x["path"] for x in manifest["files"]),
                      "portal_count":sum("/portal/" in x["path"] for x in manifest["files"])},
                     sort_keys=True))
else:
    with tarfile.open(fileobj=sys.stdout.buffer,mode="w|gz") as tar:
        for p,record in zip(FILES,manifest["files"]):
            raw=p.read_bytes()
            if hashlib.sha256(raw).hexdigest()!=record["sha256"]:
                raise RuntimeError("Source changed during export")
            info=tarfile.TarInfo(record["path"])
            info.size=len(raw);info.mode=0o600;info.mtime=0;info.uid=0;info.gid=0
            tar.addfile(info,io.BytesIO(raw))
        doc=json.dumps(manifest,sort_keys=True,ensure_ascii=False).encode("utf-8")
        info=tarfile.TarInfo("V91_AGENT_MANIFEST.json")
        info.size=len(doc);info.mode=0o600;info.mtime=0;info.uid=0;info.gid=0
        tar.addfile(info,io.BytesIO(doc))
