"""Save a SECOND V91 agents archive on the independent cPanel host.

Input is the already verified VPS backup over SSH; never reads/writes V91 source
and never touches a webroot, Django, user content or background services.
"""
import hashlib, json, os, stat, sys, tarfile
from pathlib import Path

EXPECTED_SHA="4b825f80e06d632d5aac1717f82fac32b731ca89247a45b48f2222bdd86c858c"
ROOT=Path("/home/zomorod2/.v91_agents_safety_copy")
ARCHIVE=ROOT/"v91-master-and-site-agents-20261018.tar.gz"
MAX_BYTES=1_000_000
if ROOT.is_symlink() or ARCHIVE.is_symlink() or not str(ROOT).startswith("/home/zomorod2/.v91_agents_"):
    raise SystemExit("INVALID_PRIVATE_BACKUP_DESTINATION")
if not ROOT.exists():
    ROOT.mkdir(mode=0o700)
if not ROOT.is_dir() or (ROOT.stat().st_mode & 0o077):
    raise SystemExit("BACKUP_DIR_NOT_PRIVATE")
status="existing_verified" if ARCHIVE.exists() else "created_and_verified"
if not ARCHIVE.exists():
    fd=os.open(str(ARCHIVE),os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    try:
        with os.fdopen(fd,"wb") as f:
            bytes_received=0
            while True:
                chunk=sys.stdin.buffer.read(32768)
                if not chunk:break
                bytes_received+=len(chunk)
                if bytes_received>MAX_BYTES:raise ValueError("ARCHIVE_TOO_LARGE")
                f.write(chunk)
            f.flush()
            os.fsync(f.fileno())
    except BaseException:
        try:ARCHIVE.unlink()
        except OSError:pass
        raise
if not ARCHIVE.is_file() or ARCHIVE.is_symlink():
    raise SystemExit("INVALID_BACKUP_FILE")
digest=hashlib.sha256(ARCHIVE.read_bytes()).hexdigest()
if digest!=EXPECTED_SHA:
    # Never delete/overwrite a preexisting conflicting archive.
    raise SystemExit("SOURCE_ARCHIVE_SHA256_MISMATCH")
try:
    with tarfile.open(ARCHIVE,mode="r:gz") as f:
        members=f.getmembers()
        if len(members)!=204 or members[-1].name!="V91_AGENT_MANIFEST.json":
            raise ValueError("INVALID_MANIFEST_COUNT")
        manifest=json.load(f.extractfile(members[-1]))
        rows=manifest.get("files",[])
        refs={r["path"]:r for r in rows}
        if manifest.get("file_count")!=203 or len(refs)!=203:
            raise ValueError("WRONG_FILE_COUNT")
        seen=set()
        for entry in members[:-1]:
            name=entry.name
            if not entry.isfile() or name.startswith("/") or ".." in Path(name).parts or name in seen or name not in refs:
                raise ValueError("UNSAFE_OR_UNKNOWN_FILE")
            raw=f.extractfile(entry).read()
            if len(raw)!=refs[name]["bytes"] or hashlib.sha256(raw).hexdigest()!=refs[name]["sha256"]:
                raise ValueError("RESTORE_HASH_FAILURE")
            seen.add(name)
        if len(seen)!=203 or seen!=set(refs):
            raise ValueError("INCOMPLETE_BACKUP")
except Exception:
    # Preserve file for investigation; NEVER authorize source deletion on failure.
    raise
print(json.dumps({"result":status,"host":"cpanel","source_host":"vps",
                  "source_untouched":True,"active_websites_untouched":True,
                  "archive_sha256":digest,"archive_bytes":ARCHIVE.stat().st_size,
                  "verified_restore_members":len(seen),
                  "path":str(ARCHIVE),"may_delete_original":False},
                 sort_keys=True))
