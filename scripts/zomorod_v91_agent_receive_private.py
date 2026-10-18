"""VPS-private receiver for V91 agent export. Never touches a live site."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import sys
import tarfile
import tempfile

MAX_COMPRESSED=50*1024*1024
MAX_RAW=30*1024*1024
HOME=Path.home().resolve()
if not str(HOME).startswith("/home/") or "public" in str(HOME):
    raise SystemExit("REJECTED: unexpected VPS home")
BASE=HOME/".private_zomorod_v91_agents"
if BASE.is_symlink():
    raise SystemExit("REJECTED: backup target is symlink")
BASE.mkdir(mode=0o700,parents=False,exist_ok=True)
if BASE.stat().st_mode & 0o077:
    raise SystemExit("REJECTED: target directory is not private")
STAGE=Path(tempfile.mkdtemp(prefix=".incoming_v91_",dir=BASE))
final=BASE/("v91_master_agents_20261018_run"+os.environ.get("GITHUB_RUN_ID","unknown"))
try:
    if final.exists() or final.is_symlink():
        raise RuntimeError("Refusing to overwrite a prior preserved copy")
    path=STAGE/"agents.tar.gz"
    digest=hashlib.sha256()
    size=0
    with path.open("xb") as output:
        os.chmod(path,0o600)
        while chunk:=sys.stdin.buffer.read(256*1024):
            size+=len(chunk)
            if size>MAX_COMPRESSED:
                raise RuntimeError("Archive exceeds maximum transfer limit")
            digest.update(chunk)
            output.write(chunk)
        output.flush()
        os.fsync(output.fileno())
    expected={}
    seen={}
    all_bytes=0
    with tarfile.open(path,mode="r:gz") as arc:
        members=arc.getmembers()
        if not members or members[-1].name!="V91_AGENT_MANIFEST.json":
            raise RuntimeError("Missing final integrity manifest")
        meta=arc.extractfile(members[-1])
        manifest=json.loads(meta.read())
        rows=manifest["files"]
        if len(rows)!=manifest["file_count"] or not 40<len(rows)<3000:
            raise RuntimeError("Unexpected manifest file count")
        expected={x["path"]:x for x in rows}
        if len(expected)!=len(rows):
            raise RuntimeError("Duplicate source paths")
        if len(members)!=len(rows)+1:
            raise RuntimeError("Archive/manifest count mismatch")
        recovered=STAGE/"recovered_source"
        recovered.mkdir(mode=0o700)
        for item in members[:-1]:
            name=item.name
            parts=Path(name).parts
            if (not item.isfile() or not parts or ".." in parts
                    or name.startswith("/") or "\\" in name
                    or (parts[0]!="zomorodmelal" and name not in
                        ("RELEASE_CHECKLIST_V91_FA.md","V91_EXECUTION_AND_REMAINING_FA.md"))):
                raise RuntimeError("Unsafe or unexpected archive member")
            if name not in expected or name in seen or item.size>5*1024*1024:
                raise RuntimeError("Missing manifest entry or unsafe file")
            binary=arc.extractfile(item).read()
            if len(binary)!=expected[name]["bytes"]:
                raise RuntimeError("File length mismatch")
            if hashlib.sha256(binary).hexdigest()!=expected[name]["sha256"]:
                raise RuntimeError("File digest mismatch")
            all_bytes+=len(binary)
            if all_bytes>MAX_RAW:
                raise RuntimeError("Expanded archive exceeds safety limit")
            target=recovered.joinpath(*parts)
            target.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
            with target.open("xb") as out:
                os.chmod(target,0o600)
                out.write(binary)
            seen[name]=True
        if set(seen)!=set(expected):
            raise RuntimeError("Archive omitted source files")
        for required in ("zomorodmelal/portal/agent_engine.py",
                         "zomorodmelal/portal/management/commands/run_site_master.py",
                         "zomorodmelal/portal/management/commands/run_site_agents.py",
                         "zomorodmelal/site_master/vendor/master_gen64/controller.py"):
            if required not in seen:
                raise RuntimeError("Missing core master-agent module")
    (STAGE/"V91_AGENT_MANIFEST.json").write_text(
        json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    (STAGE/"SHA256SUMS").write_text(digest.hexdigest()+"  agents.tar.gz\n",encoding="ascii")
    path.rename(STAGE/"agents.tar.gz")
    STAGE.rename(final)
    print(json.dumps({"state":"VERIFIED_PRIVATE_COPY","directory":str(final),
                      "source":"saeit_v91/zomorodmelal","archive_bytes":size,
                      "raw_bytes":all_bytes,"verified_files":len(seen),
                      "sha256":digest.hexdigest(),
                      "working_copy":str(final/"recovered_source"),
                      "original_untouched":True,"live_site_untouched":True,
                      "not_activated":True},sort_keys=True))
except Exception:
    shutil.rmtree(STAGE,ignore_errors=True)
    raise
