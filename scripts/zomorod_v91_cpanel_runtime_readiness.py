"""No-write preflight on cPanel V91. Does not import Django or touch live site."""
import ast,hashlib,json,os,resource,stat,sys,time
from pathlib import Path
ROOT=Path("/home/zomorod2/saeit_v91/zomorodmelal")
CHECKS={
  "master_command": ROOT/"portal/management/commands/run_site_master.py",
  "agents_command": ROOT/"portal/management/commands/run_site_agents.py",
  "master_bridge": ROOT/"site_master/bridge.py",
  "gen64_controller": ROOT/"site_master/vendor/master_gen64/controller.py",
  "agents_permission": ROOT/"portal/runtime_permissions.py",
  "agents_engine": ROOT/"portal/agent_engine.py",
  "agents_services": ROOT/"portal/agent_services.py",
  "portal_models": ROOT/"portal/models.py",
  "agent_generator": ROOT/"portal/generator.py",
}
out={"kind":"V91_CPANEL_AGENT_PREFLIGHT_READONLY","root_exists":ROOT.is_dir(),"python":sys.version.split()[0],"files":{}}
for key,p in CHECKS.items():
    present=p.is_file() and not p.is_symlink()
    row={"exists":present}
    if present:
        try:
            data=p.read_bytes()
            root=ast.parse(data.decode("utf8"))
            row.update({"parse_ok":True,"size":len(data),"sha256_prefix":hashlib.sha256(data).hexdigest()[:16]})
            defs=[]
            for n in root.body:
                if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):
                    defs.append(n.name)
            row["definitions"]=defs[:25]
            if key=="agents_permission":
                flags=sorted(set(n.value for n in ast.walk(root) if isinstance(n,ast.Constant) and isinstance(n.value,str) and ("AGENT" in n.value or "MASTER" in n.value)))
                row["policy_flag_names"]=flags[:25]
        except Exception as e:
            row["parse_ok"]=False
            row["error_type"]=type(e).__name__
    out["files"][key]=row
# This check does not execute Django commands, migrations, cron, websites or wallets.
out.update({"django_or_external_calls_made":False,"source_mutated":False,"live_site_mutated":False})
print(json.dumps(out,sort_keys=True))
