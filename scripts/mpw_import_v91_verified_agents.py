"""Extract only reusable V91 master and agent engines into MojPlayWin.

The source archive is the SHA-verified private copy of the abandoned V91 draft.
This script runs on a GitHub Actions runner, never on any live website.
No files are copied from V91 databases, media, configuration or credentials.
"""
import hashlib
import io
import json
import pathlib
import sys
import tarfile

ARCHIVE_SHA256="4b825f80e06d632d5aac1717f82fac32b731ca89247a45b48f2222bdd86c858c"
SRC_PREFIX="zomorodmelal/"
DEST_PREFIX=pathlib.Path("mpw_v91_port/legacy")
MAX_BYTES=1_000_000

def permitted(rel):
    # Generation12..64 master libraries, callback bridge, and rule-based
    # editorial output generator. Django/site migrations remain excluded.
    if rel.startswith("site_master/"):
        return rel.endswith(".py")
    return rel in (
        "portal/agent_engine.py",
        "portal/generator.py",
        "portal/agent_claims.py",
        "portal/agent_run_lock.py",
    )

def main(archive):
    raw=pathlib.Path(archive).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=ARCHIVE_SHA256:
        raise SystemExit("SOURCE_ARCHIVE_HASH_MISMATCH")
    verified=[]
    with tarfile.open(fileobj=io.BytesIO(raw),mode="r:gz") as tar:
        members={m.name:m for m in tar.getmembers()}
        manifest=json.load(tar.extractfile(members["V91_AGENT_MANIFEST.json"]))
        if manifest.get("file_count")!=203:
            raise SystemExit("SOURCE_ARCHIVE_MANIFEST_COUNT_MISMATCH")
        for entry in manifest["files"]:
            source=entry["path"]
            if not source.startswith(SRC_PREFIX):
                continue
            rel=source[len(SRC_PREFIX):]
            if not permitted(rel):
                continue
            m=members.get(source)
            if m is None or not m.isfile() or m.size>MAX_BYTES:
                raise SystemExit("MISSING_SOURCE_AGENT_MODULE")
            data=tar.extractfile(m).read()
            if len(data)!=entry["bytes"] or hashlib.sha256(data).hexdigest()!=entry["sha256"]:
                raise SystemExit("SOURCE_AGENT_MODULE_INTEGRITY_ERROR")
            target=DEST_PREFIX.joinpath(*pathlib.PurePosixPath(rel).parts)
            if target.is_symlink() or target.exists():
                raise SystemExit("REFUSING_OVERWRITE_OF_PORTED_FILE")
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(data)
            verified.append({"destination":str(target),"source":source,"sha256":entry["sha256"]})
    if len(verified)<50:
        raise SystemExit("INCOMPLETE_MASTER_AGENT_GENERATION_IMPORT")
    dest=pathlib.Path("mpw_v91_port")
    dest.mkdir(exist_ok=True)
    (dest/"__init__.py").write_text('"""MojPlayWin-only port of verified V91 master and rule-based agents."""\n')
    (DEST_PREFIX/"__init__.py").write_text('"""Archived source modules from original V91."""\n')
    (DEST_PREFIX/"portal"/"__init__.py").write_text('"""V91 editorial agents for MojPlayWin review-only reuse."""\n')
    (dest/"ORIGIN.json").write_text(json.dumps({
        "source":"V91 Zomorod Melal legacy source, SHA-verified and selectively ported",
        "source_sha256":ARCHIVE_SHA256,
        "file_count":len(verified),
        "scope":"MojPlayWin main site ONLY; excluded all other sites",
        "modules":verified,
        "removed":"No source file removed; no live server updates performed",
    },indent=2,sort_keys=True)+"\n")
    print(json.dumps({"result":"MPW_MASTER_AGENT_MODULES_IMPORTED","verified_file_count":len(verified),
                      "destination":"mpw_v91_port/legacy","original_sites_unchanged":True}))

if __name__=="__main__":
    if len(sys.argv)!=2:raise SystemExit("Usage: script.py verified_archive.tar.gz")
    main(sys.argv[1])
