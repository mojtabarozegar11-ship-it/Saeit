"""Exercise preserved V91 agent content generator with a synthetic payload only."""
import hashlib
import json
import os
from pathlib import Path
import resource
import sys
import time
root=Path("/home/githubops/.private_zomorod_v91_agents/v91_master_agents_20261018_run39086083902")
base=root/"recovered_source"/"zomorodmelal"
manifest=json.loads((root/"V91_AGENT_MANIFEST.json").read_text())
checks={p["path"]:p["sha256"] for p in manifest["files"]}
for rel in ("portal/agent_engine.py","portal/generator.py"):
    f=base/rel
    assert f.is_file() and not f.is_symlink()
    assert checks["zomorodmelal/"+rel]==hashlib.sha256(f.read_bytes()).hexdigest()
resource.setrlimit(resource.RLIMIT_CPU,(8,9))
resource.setrlimit(resource.RLIMIT_FSIZE,(0,0))
sys.dont_write_bytecode=True
def guard(event,args):
    if event=="open":
        mode=str(args[1]) if len(args)>1 else "r"
        flags=args[2] if len(args)>2 else 0
        if any(x in mode for x in ("w","a","x","+")) or (
           isinstance(flags,int) and flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND)
        ):
            raise PermissionError("Denied")
    if event.startswith("socket.") or event in ("subprocess.Popen","os.system","os.fork","os.exec","os.remove","os.rename","os.mkdir","os.chdir","ctypes.dlopen"):
        raise PermissionError("Denied")
sys.addaudithook(guard)
sys.path.insert(0,str(base))
started=time.monotonic()
try:
    from portal.agent_engine import build_output
    long_body=("This is a synthetic agriculture operations test about planning water use, verifying field records, "
               "monitoring irrigation performance, comparing costs and reporting uncertainty. ")*9
    src=[{"title":"Synthetic example source","url":"https://example.org/"}]
    for kind in ("article","guide","education"):
        try:
            output=build_output(kind,"Synthetic test: agricultural planning",
                                "Synthetic test summary for field economics.",long_body,src,"en")
            print(json.dumps({"stage":"V91_AGENT_CONTENT_ENGINE","status":"OK","output_kind":kind,
                              "result_type":type(output).__name__,
                              "elapsed_ms":int((time.monotonic()-started)*1000),
                              "live_content_created":False,
                              "persisted":False}))
            raise SystemExit(0)
        except (ValueError,TypeError) as exc:
            failure=type(exc).__name__
    print(json.dumps({"stage":"V91_AGENT_CONTENT_ENGINE","status":"INPUT_VALIDATION_REJECTED",
                      "error_type":failure,"live_content_created":False,"persisted":False}))
except Exception as exc:
    print(json.dumps({"stage":"V91_AGENT_CONTENT_ENGINE","status":"NOT_READY",
                      "error_type":type(exc).__name__,"live_content_created":False,
                      "persisted":False}))
    raise SystemExit(3)
