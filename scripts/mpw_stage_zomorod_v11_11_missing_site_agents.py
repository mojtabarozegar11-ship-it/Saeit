"""Stage the 11 MojPlayWin-specific website audit roles as private, verified code.

No writes to Zomorod, MojPlayWin webroots, Django, databases or existing jobs.
"""
import hashlib
import io
import json
import os
import shutil
import sys
import tarfile
import tempfile
from pathlib import Path

PARENT=Path("/home/zomorod2/.private_mojplaywin_main_agents")
DEST=PARENT/"site_health_v11_port_20261018"
NAMES={"mpw_v91_port/site_health_v11.py",
       "mpw_v91_port/heritage/zomorod_v11_site_agents_reference.php"}
LIMIT=100000
def fail(msg):raise RuntimeError(msg)

def main():
    if not PARENT.is_dir() or PARENT.is_symlink() or (PARENT.stat().st_mode&0o077):
        fail("PRIVATE_PARENT_UNAVAILABLE")
    if DEST.exists() or DEST.is_symlink():
        fail("ALREADY_STAGED_NO_OVERWRITE")
    data=sys.stdin.buffer.read(LIMIT+1)
    if not data or len(data)>LIMIT:fail("ARCHIVE_OVERSIZE")
    stage=Path(tempfile.mkdtemp(prefix=".incoming-mpw-v11-",dir=str(PARENT)))
    try:
        with tarfile.open(fileobj=io.BytesIO(data),mode="r:gz") as archive:
            members={m.name:m for m in archive.getmembers()}
            if set(members)!=NAMES|{"MANIFEST.json"}:fail("UNEXPECTED_FILES")
            meta=json.load(archive.extractfile(members["MANIFEST.json"]))
            checks=meta.get("sha256",{})
            if set(checks)!=NAMES or meta.get("tenant")!="mojplaywin-main" or meta.get("site_writes") is not False:
                fail("BAD_MANIFEST")
            for name in NAMES:
                m=members[name]
                if not m.isfile() or m.size>30000 or m.size<=0:fail("INVALID_MEMBER")
                raw=archive.extractfile(m).read()
                if hashlib.sha256(raw).hexdigest()!=checks[name]:fail("HASH_MISMATCH")
                target=stage/name
                target.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
                with target.open("xb") as out:
                    os.fchmod(out.fileno(),0o600)
                    out.write(raw)
        (stage/"manifest.json").write_text(json.dumps(meta,sort_keys=True),encoding="utf8")
        os.chmod(stage/"manifest.json",0o600)
        stage.rename(DEST)
        os.chmod(DEST,0o700)
        print(json.dumps({"status":"MPW_11_MISSING_V11_AGENTS_COPIED_PRIVATE",
            "role_count":11,"verified_source_count":len(NAMES),
            "origin_reference_sha256":checks["mpw_v91_port/heritage/zomorod_v11_site_agents_reference.php"],
            "new_private_location":str(DEST),
            "live_sites_modified":False,"factory_modified":False,
            "scheduled":False},sort_keys=True))
    except BaseException:
        if stage.exists():shutil.rmtree(stage,ignore_errors=True)
        raise
if __name__=="__main__":main()
