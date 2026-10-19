"""Preserve exact live Zomorod Django agent implementations privately for MojPlayWin review.

Copy SOURCE CODE ONLY from a strict SHA-pinned allowlist to a private non-web
directory. Never import the original Django modules, run migrations, write the
source site, connect a DB, publish, or modify cron/Passenger.
"""
import hashlib,json,os,shutil
from pathlib import Path

SRC=Path("/home/zomorod2/Saeit")
PARENT=Path("/home/zomorod2/.private_mojplaywin_main_agents")
DEST=PARENT/"zomorod_django_agent_sources_20261018"
FILES={
"core/agent_registry.py":"6ae4bb9218aa03a80747b71876411a0dbff1d082c4dc9ff2c4049abf739747b6",
"core/economic_master_agent.py":"c59a24fe2a8aa2c6b9e3c3ef94248e9cf2534da5dd84cd26bfb10995bf6b4e67",
"core/knowledge_agent.py":"d65d5cf9c0cee53503e835cfd64dd4f8af5afe060b3493a65b72da84493978bf",
"core/knowledge_quality.py":"1bb75e447968ac7b25975facb28f02f8642d712b9d0fe5db5d4b87f2a5af66ef",
"core/company_activity_agent.py":"aadfaf64118146d24e034fb463c5da92765973b39b38eeb5be8292cc86673924",
"core/weather_agent.py":"dfae110114935e054e5b0a8e2acc52482c7592b3ebed9d44e57b86ae1674672f",
"core/newsletter_engine.py":"6bb1cfa3425b2382b5eba5584e5f96ccda2285ecef078bfbd2b26b477f038d6c",
"core/worker_runner.py":"3b890e7f2d9f383130a4aa711f6b251ee124a7a903ebdd2a29acf3278368bbee",
"core/master_agent_capability_pack.py":"fd57da5097d5a7dff96440bc22e9c116bbfd791d00069c1024294be4a9bf626d",
"core/management/commands/knowledge_agent_generate.py":"365827aa157840ffc67975b30023c46c5d172d7b4546a187acc6f8f0bc88a751",
}
def must(v,msg):
    if not v:raise RuntimeError(msg)
def main():
    must(SRC.is_dir() and not SRC.is_symlink(),"SOURCE_NOT_SAFE")
    must(PARENT.is_dir() and not PARENT.is_symlink() and PARENT.stat().st_mode&0o077==0,"PRIVATE_PARENT_UNAVAILABLE")
    must(not DEST.exists() and not DEST.is_symlink(),"NO_OVERWRITE_OF_EXISTING_COPY")
    for rel,expected in FILES.items():
        src=SRC/rel
        must(src.is_file() and not src.is_symlink(),"SOURCE_FILE_MISSING")
        data=src.read_bytes()
        must(len(data)<100000 and hashlib.sha256(data).hexdigest()==expected,"SOURCE_SHA_CHANGED")
    tmp=PARENT/".incoming-zomorod-django-agents-20261018"
    must(not tmp.exists() and not tmp.is_symlink(),"STAGING_COLLISION")
    tmp.mkdir(mode=0o700)
    try:
        for rel,expected in FILES.items():
            path=tmp/"reference"/rel
            path.parent.mkdir(parents=True,mode=0o700,exist_ok=True)
            fd=os.open(str(path),os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
            with os.fdopen(fd,"wb") as f:
                f.write((SRC/rel).read_bytes())
            must(hashlib.sha256(path.read_bytes()).hexdigest()==expected,"COPY_INTEGRITY_FAILED")
        meta={"tenant":"mojplaywin-main","role":"unexecuted_original_Zomorod_Django_source_reference",
              "files":FILES,"site_zomorod_original_unchanged":True,
              "do_not_run_or_import_original_modules":True,
              "source_database_not_copied":True}
        p=tmp/"manifest.json"
        p.write_text(json.dumps(meta,ensure_ascii=False,indent=2,sort_keys=True))
        os.chmod(p,0o600)
        tmp.rename(DEST)
        print(json.dumps({"status":"ZOMOROD_LIVE_AGENT_SOURCE_COPIED_TO_MPW_PRIVATE",
                          "copied_exact_live_modules":len(FILES),
                          "destination":str(DEST),
                          "all_sha256_verified":True,
                          "live_sites_modified":False,"factory_modified":False,
                          "operational_agents_added":0,
                          "content_quality_adapter_next":True},sort_keys=True))
    except BaseException:
        if tmp.exists():shutil.rmtree(tmp,ignore_errors=True)
        raise
if __name__=="__main__":main()
