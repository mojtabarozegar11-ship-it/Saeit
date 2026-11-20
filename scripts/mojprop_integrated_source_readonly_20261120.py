"""Exact source identity census of three previously observed owner roots.
No imports of live Django, no credentials or file content in output.
"""
import ast
import hashlib
import json
import os
import pwd
import stat
from pathlib import Path
HOME=Path("/home/zomorod2")
ROOTS={"public":HOME/"mojplaywin.com","staging":HOME/"Saeit-staging","integrated":HOME/"Saeit-mojplaywin-integrated-20261119"}
CANDIDATE="ac8c8553579983e82bac78c492658359b2a172bd"
EXPECTED={
"config/settings.py":"0247dbb157986d79543db91bc41b815c933e68d3",
"config/urls.py":"9f8266bba06377cb9c6f54e437cab7fac667ee91",
"core/moj_prop_views.py":"64c8d1aac5ef476620440f764e21c6c42cbb56bb",
"prop_firm/models.py":"ac4aa23d58fb4d0ecb33a836b12e37cf6ca6b454",
"prop_firm/simulation_engine.py":"6ab28b98c8e346a84169816fe8516ec0006709fd",
"prop_firm/simulation_checkout_views.py":"b2ec6468e883796c40a4263fffe9088bfabc9c5b",
"prop_firm/simulation_payment_views.py":"cd408deb6333e15c97ed620c5ed123aa0f3fd473",
"prop_firm/simulation_upgrade_guard.py":"2d74b658272b5420bc69be3eee5406fb2cd795fc",
"prop_firm/migrations/0017_simulation_event_head.py":"653d5df5d89033a76e353172d892c3e5142466f3",
"core/templates/mojplaywin/moj_prop_simulation.html":"112f947a9a1ab58eb7c9b0dad46d1077aa9cb174"}
def read_fixed(path):
    if path.resolve()!=path:
        return None
    fd=os.open(str(path),os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        before=os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_uid!=os.geteuid() or before.st_size>2_000_000:
            return None
        with os.fdopen(os.dup(fd),"rb") as f:
            data=f.read(2_000_001)
        after=os.fstat(fd)
        if len(data)!=before.st_size or (before.st_size,before.st_mtime_ns,before.st_ino)!=(after.st_size,after.st_mtime_ns,after.st_ino):
            return None
        return data
    finally:
        os.close(fd)
def classify(data,expected):
    if data is None:return "unavailable"
    digest=hashlib.sha1(("blob "+str(len(data))+"\0").encode()+data).hexdigest()
    return "matches_candidate" if digest==expected else "different"
def wsgi_summary(data):
    if data is None:return {"ast_valid":False}
    try:
        tree=ast.parse(data)
        literals={n.value for n in ast.walk(tree) if isinstance(n,ast.Constant) and isinstance(n.value,str)}
        return {"ast_valid":True,"exact_root_literals":{label:str(path) in literals for label,path in ROOTS.items()},
                "django_entrypoint":any(isinstance(n,ast.Name) and n.id=="get_wsgi_application" for n in ast.walk(tree))}
    except (SyntaxError,ValueError):
        return {"ast_valid":False}
def audit():
    out={"read_only":True,"database_accessed":False,"raw_source_emitted":False,"release_authorized":False,"effective_worker_proven":False,"candidate":CANDIDATE}
    if os.geteuid()==0 or pwd.getpwuid(os.geteuid()).pw_name!="zomorod2":
        return out
    roots={}
    for label,root in ROOTS.items():
        result={"directory_present":root.is_dir() and root.resolve()==root,"files":{}}
        if result["directory_present"]:
            for name,expected in EXPECTED.items():
                try:result["files"][name]=classify(read_fixed(root/name),expected)
                except FileNotFoundError:result["files"][name]="missing"
                except (OSError,ValueError):result["files"][name]="unavailable"
        roots[label]=result
    out["roots"]=roots
    try:out["public_wsgi"]=wsgi_summary(read_fixed(ROOTS["public"]/"passenger_wsgi.py"))
    except (OSError,ValueError):out["public_wsgi"]={"ast_valid":False}
    return out
if __name__=="__main__":
    print("MOJPROP_INTEGRATED_SOURCE_READONLY="+json.dumps(audit(),sort_keys=True))
