"""Bounded read-only real V91 master Gen64 smoke test, never touch live sites."""
import hashlib
import json
import os
from pathlib import Path
import resource
import sys
import time

ROOT=Path("/home/zomorod2/saeit_v91")
SOURCE=ROOT/"zomorodmelal"
check=[
"site_master/bridge.py",
"site_master/vendor/master_gen64/controller.py",
"site_master/vendor/master_gen64/cycles.py",
"site_master/vendor/master_gen56/controller.py",
"portal/agent_engine.py",
]
for rel in check:
    f=SOURCE/rel
    data=f.read_bytes()
    assert data and f.is_file() and not f.is_symlink()
assert ROOT.is_dir() and SOURCE.is_dir()
resource.setrlimit(resource.RLIMIT_CPU,(8,9))
resource.setrlimit(resource.RLIMIT_FSIZE,(0,0))
resource.setrlimit(resource.RLIMIT_NOFILE,(64,64))
try:
    soft,hard=resource.getrlimit(resource.RLIMIT_AS)
    resource.setrlimit(resource.RLIMIT_AS,(min(soft,768*1024*1024) if soft>0 else 768*1024*1024,hard))
except (ValueError,OSError):
    pass
os.environ["PYTHONDONTWRITEBYTECODE"]="1"
os.environ.pop("DJANGO_SETTINGS_MODULE",None)
events=[]
def deny_side_effects(event,args):
    if event=="open":
        mode=args[1] if len(args)>1 else "r"
        flags=args[2] if len(args)>2 else 0
        if any(x in str(mode) for x in ("w","a","x","+")) or (
            isinstance(flags,int) and (flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))
        ):
            raise PermissionError("Master Gen64 smoke: file modifications denied")
    if event in (
        "socket.__new__","socket.connect","socket.getaddrinfo",
        "subprocess.Popen","os.system","os.fork","os.exec",
        "os.remove","os.rename","os.mkdir","os.chmod","os.chown","os.symlink",
        "os.link","os.truncate","os.utime","os.chdir","ctypes.dlopen",
    ):
        raise PermissionError("Master Gen64 smoke: side-effect denied")
sys.addaudithook(deny_side_effects)
sys.dont_write_bytecode=True
sys.path.insert(0,str(SOURCE))
t=time.monotonic()
try:
    from site_master.bridge import route_once
    count=[0]
    def clean_callback(*args,**kwargs):
        count[0]+=1
        return {"status":"OK","dry_run":True}
    result=route_once("v91-gen64-offline-smoke-20261018",clean_callback)
    print(json.dumps({"stage":"CPANEL_GEN64_BOUNDED_SMOKE","ok":count[0]>0,
                      "callback_count":count[0],
                      "result_type":type(result).__name__,
                      "elapsed_ms":int((time.monotonic()-t)*1000),
                      "live_site_untouched":True,"persistent_service_activated":False}))
    if count[0]<1:
        raise SystemExit(4)
except Exception as exc:
    print(json.dumps({"stage":"GEN64_BOUNDED_SMOKE","ok":False,
                      "error_type":type(exc).__name__,
                      "live_site_untouched":True,
                      "persistent_service_activated":False}))
    raise SystemExit(3)
