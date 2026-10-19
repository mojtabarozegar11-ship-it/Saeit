"""Stage a SHA-verified MojPlayWin-only staff chart release candidate privately.

NO touch to document roots, public web pages, shared Django/Passenger, DB, factory,
or the existing operational V91 hourly worker.
"""
import hashlib,io,json,os,stat,sys,tarfile,tempfile,shutil
from pathlib import Path

HOME=Path("/home/zomorod2")
PRIVATE=HOME/".private_mojplaywin_main_agents"
DEST=PRIVATE/"management_release_16_agents_20261018"
FILES={
"command_center/mpw_v91_agent_metrics.py",
"command_center/mpw_v91_agent_views.py",
"command_center/mpw_v11_site_agent_charts.py",
"command_center/mpw_zomorod_management_charts.py",
"mpw_v91_port/site_health_v11.py",
"command_center/templates/command_center/mpw_v91_agent_performance.html",
"command_center/templates/command_center/dashboard.html",
"command_center/views.py",
"command_center/urls.py",
"core/admin.py",
"core/templates/admin/core/agent/change_list.html",
"core/templates/admin/core/agent/mpw_v91_performance.html",
"config/urls.py",
"core/mojplaywin_v91_agent_views.py",
}
def abort(message):
    raise RuntimeError(message)

def safe_dir(path):
    return path.is_dir() and not path.is_symlink() and path.stat().st_mode&0o077==0
def main():
    if not safe_dir(PRIVATE) or DEST.exists() or DEST.is_symlink():
        abort("UNSAFE_OR_ALREADY_STAGED")
    raw=sys.stdin.buffer.read(500001)
    if not raw or len(raw)>500000:
        abort("ARCHIVE_LENGTH_NOT_ALLOWED")
    stage=Path(tempfile.mkdtemp(prefix=".incoming_mpw_chart_",dir=PRIVATE))
    try:
        bytes_total=0
        found=set()
        with tarfile.open(fileobj=io.BytesIO(raw),mode="r:gz") as archive:
            items=archive.getmembers()
            docs={m.name:m for m in items}
            if len(items)!=len(FILES)+1 or "MANIFEST.json" not in docs:
                abort("REQUIRED_MANIFEST_NOT_PRESENT")
            manifest=json.load(archive.extractfile(docs["MANIFEST.json"]))
            checks=manifest.get("sha256",{})
            if set(checks)!=FILES or len(checks)!=len(FILES):
                abort("MANIFEST_PATHS_CHANGED")
            for rel in sorted(FILES):
                item=docs.get("files/"+rel)
                if item is None or not item.isfile() or item.size>180000:
                    abort("SOURCE_MODULE_MISSING")
                if any(part in (".","..") or part.startswith(".") for part in Path(rel).parts):
                    abort("UNSAFE_SOURCE_NAME")
                payload=archive.extractfile(item).read()
                bytes_total+=len(payload)
                if bytes_total>500000 or hashlib.sha256(payload).hexdigest()!=checks[rel]:
                    abort("INTEGRITY_ERROR")
                target=stage/"files"/rel
                target.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
                with target.open("xb") as f:
                    os.fchmod(f.fileno(),0o600)
                    f.write(payload)
                found.add(rel)
            if set(docs)!=set(["MANIFEST.json"]+["files/"+p for p in FILES]):
                abort("UNEXPECTED_FILES")
        m=stage/"MANIFEST.json"
        m.write_text(json.dumps(manifest,sort_keys=True,indent=2),encoding="utf8")
        os.chmod(m,0o600)
        stage.rename(DEST)
        print(json.dumps({
            "status":"MPW_ADMIN_CHARTS_PRIVATE_STAGE_VERIFIED",
            "path":str(DEST),
            "source_files_verified":len(found),"source_bytes":bytes_total,
            "live_site_modified":False,"factory_modified":False,"subsites_modified":False,
            "existing_hourly_worker_modified":False,
            "web_panel_published":False,"shared_passenger_restarted":False,
        },sort_keys=True))
    except BaseException:
        if stage.exists():shutil.rmtree(stage,ignore_errors=True)
        raise
if __name__=="__main__":
    main()
