"""Inspect preserved V91 agent commands without executing their code or touching sites."""
import ast
import hashlib
import json
from pathlib import Path
ROOT=Path("/home/githubops/.private_zomorod_v91_agents/v91_master_agents_20261018_run39086083902")
SOURCE=ROOT/"recovered_source"/"zomorodmelal"
PROBES=[
"portal/agent_engine.py",
"portal/agent_services.py",
"portal/agent_claims.py",
"portal/agent_run_lock.py",
"portal/management/commands/run_site_master.py",
"portal/management/commands/run_site_agents.py",
"portal/tests_master.py",
"site_master/__init__.py",
"site_master/bridge.py",
"site_master/private_storage.py",
"site_master/research.py",
"site_master/vendor/master_gen64/controller.py",
"site_master/vendor/master_gen64/cycles.py",
"portal/models.py",
]
assert ROOT.is_dir() and SOURCE.is_dir()
manifest=json.loads((ROOT/"V91_AGENT_MANIFEST.json").read_text())
indexed={d["path"]:d for d in manifest["files"]}
results=[]
for path in PROBES:
    f=SOURCE/path
    if not f.is_file() or f.is_symlink():
        results.append({"path":path,"status":"missing"})
        continue
    data=f.read_bytes()
    expected=indexed.get("zomorodmelal/"+path)
    assert expected and hashlib.sha256(data).hexdigest()==expected["sha256"]
    text=data.decode("utf8",errors="replace")
    tree=ast.parse(text)
    imports=[]
    for n in ast.walk(tree):
        if isinstance(n,ast.ImportFrom):
            imports.append({"module":n.module,"names":[z.name for z in n.names][:12]})
        elif isinstance(n,ast.Import):
            imports.extend({"module":z.name} for z in n.names)
    actions=[]
    for n in tree.body:
        if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):
            actions.append({"type":n.__class__.__name__,"name":n.name,"methods":[x.name for x in n.body if isinstance(x,(ast.FunctionDef,ast.AsyncFunctionDef))][:25]} if isinstance(n,ast.ClassDef) else {"type":n.__class__.__name__,"name":n.name})
    results.append({"path":path,"size":len(data),"imports":imports[:50],"defs":actions[:70]})

def summarize_callable(rel, search_name):
    src=(SOURCE/rel).read_text(encoding="utf-8")
    tree=ast.parse(src)
    def signature(node):
        args=node.args
        return {
            "args": [arg.arg for arg in args.posonlyargs+args.args+args.kwonlyargs],
            "required_positional": len(args.posonlyargs+args.args)-len(args.defaults),
            "keywords": [arg.arg for arg in args.kwonlyargs],
            "has_vararg": args.vararg is not None,
            "has_kwarg": args.kwarg is not None,
            "call_targets": sorted({ast.unparse(n.func)[:95] for n in ast.walk(node) if isinstance(n,ast.Call)})[:55],
            "raise_types": sorted({ast.unparse(n.exc)[:95] for n in ast.walk(node) if isinstance(n,ast.Raise) and n.exc is not None})[:15],
        }
    for n in tree.body:
        if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name==search_name:
            return signature(n)
        if isinstance(n,ast.ClassDef):
            for fn in n.body:
                if isinstance(fn,(ast.FunctionDef,ast.AsyncFunctionDef)) and fn.name==search_name:
                    return signature(fn)
    return {"status":"function_not_found"}
details={}
for rel,fn in [
  ("portal/management/commands/run_site_master.py","handle"),
  ("portal/management/commands/run_site_agents.py","handle"),
  ("site_master/bridge.py","route_once"),
  ("site_master/bridge.py","new_controller"),
  ("site_master/vendor/master_gen64/controller.py","run"),
  ("site_master/vendor/master_gen64/controller.py","awaken"),
  ("portal/agent_engine.py","build_output"),
]:
    details[rel+"::"+fn]=summarize_callable(rel,fn)
print(json.dumps({"status":"ok","functions":details},ensure_ascii=False))
