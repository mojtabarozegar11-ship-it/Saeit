"""Determine whether legacy site agents can run without touching production DB."""
import ast,importlib.util,json,os,sys
from pathlib import Path
root=Path("/home/zomorod2/saeit_v91/zomorodmelal")
def parse(p):
    return ast.parse(p.read_text(encoding="utf-8"))
result={"kind":"V91_LAUNCH_GATES_READ_ONLY","python_version":sys.version.split()[0]}
for key,rel in (
  ("site_agents","portal/management/commands/run_site_agents.py"),
  ("site_master","portal/management/commands/run_site_master.py"),
  ("permissions","portal/runtime_permissions.py"),
):
    t=parse(root/rel)
    args=[]
    flags=set()
    for n in ast.walk(t):
        if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=="add_argument":
            strings=[x.value for x in n.args if isinstance(x,ast.Constant) and isinstance(x.value,str)]
            args.extend(s for s in strings if s.startswith("--"))
        if isinstance(n,ast.Constant) and isinstance(n.value,str) and any(z in n.value for z in ("SAEIT_","OWNER_","SITE_AGENTS")):
            flags.add(n.value[:100])
    result[key]={"cli_options":sorted(set(args))[:50],"policy_names":sorted(flags)[:45],
                 "has_explicit_dry_run": any("dry" in a for a in args)}
result["django_importable"]=importlib.util.find_spec("django") is not None
result["manage_py_available"]=(root/"manage.py").is_file()
result["settings_candidates"]=sorted(p.name for p in root.iterdir() if p.is_dir() and (p/"settings.py").exists())[:12]
result["site_root_not_public"]=not str(root).startswith("/home/zomorod2/public_html/")
result["live_db_access_attempted"]=False
result["changes"]=0
print(json.dumps(result,sort_keys=True))
