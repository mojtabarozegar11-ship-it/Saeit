"""Receive strictly MojPlayWin-scoped source into an isolated private cPanel stage.

Neither Django/Passenger nor any live website is imported, restarted, or written.
"""
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import stat
import sys
import tarfile
import tempfile

MAX_ARCHIVE_BYTES=1_500_000
MAX_EXPANDED_BYTES=3_000_000
ROOT=Path("/home/zomorod2/.private_mojplaywin_main_agents")
FINAL=ROOT/"v91_verified_main_port_20261018"

def die(message):
    raise RuntimeError(message)

def main():
    if ROOT.is_symlink() or FINAL.is_symlink():
        die("UNSAFE_PRIVATE_TARGET")
    ROOT.mkdir(mode=0o700,exist_ok=True)
    if not ROOT.is_dir() or ROOT.stat().st_mode & 0o077:
        die("PRIVATE_TARGET_NOT_PRIVATE")
    if FINAL.exists():
        die("EXISTING_STAGE_NO_OVERWRITE")
    archive=sys.stdin.buffer.read(MAX_ARCHIVE_BYTES+1)
    if not archive or len(archive)>MAX_ARCHIVE_BYTES:
        die("INVALID_STAGE_ARCHIVE_LENGTH")
    stage=Path(tempfile.mkdtemp(prefix=".incoming_mpw_v91_",dir=ROOT))
    try:
        seen=set()
        size=0
        with tarfile.open(fileobj=io.BytesIO(archive),mode="r:gz") as tar:
            members=tar.getmembers()
            for member in members:
                pure=Path(member.name)
                if (not member.isfile() or member.size>MAX_ARCHIVE_BYTES
                    or not pure.parts or pure.parts[0]!="mpw_v91_port"
                    or any(part in (".","..") or part.startswith(".") for part in pure.parts)
                    or pure.suffix not in (".py",".json")
                    or member.name in seen):
                    die("UNSAFE_STAGE_ARCHIVE_ENTRY")
                seen.add(member.name)
                size+=member.size
                if size>MAX_EXPANDED_BYTES:
                    die("STAGE_TOO_LARGE")
                destination=stage.joinpath(*pure.parts)
                destination.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
                data=tar.extractfile(member).read()
                if len(data)!=member.size:
                    die("ARCHIVE_TRUNCATED")
                with destination.open("xb") as f:
                    os.chmod(destination,0o600)
                    f.write(data)
        manifest=json.loads((stage/"mpw_v91_port"/"ORIGIN.json").read_text())
        entries=manifest.get("modules",[])
        expected={x["destination"]:x for x in entries}
        if manifest.get("file_count",0)<70 or len(entries)!=len(expected):
            die("ORIGINAL_SOURCE_PROVENANCE_MISSING")
        if not set(expected).issubset(seen):
            die("MISSING_VERIFIED_V91_MODULE")
        for name,row in expected.items():
            p=stage.joinpath(*Path(name).parts)
            if hashlib.sha256(p.read_bytes()).hexdigest()!=row["sha256"]:
                die("V91_SOURCE_FILE_INTEGRITY_FAILURE")
        # Atomic publication to a PRIVATE NON-WEB ROOT ONLY.
        stage.rename(FINAL)
        print(json.dumps({"status":"MPW_V91_PRIVATE_STAGE_VERIFIED",
                          "path":str(FINAL),
                          "original_v91_modules_verified":len(expected),
                          "all_files_in_stage":len(seen),
                          "staging_bytes":size,
                          "source_archive_sha256":manifest["source_sha256"],
                          "site_modified":False,"passenger_restarted":False,
                          "factory_modified":False,"subsites_modified":False,
                          "production_route_enabled":False},sort_keys=True))
    except Exception:
        if stage.exists():
            shutil.rmtree(stage,ignore_errors=True)
        raise

if __name__=="__main__":
    main()
