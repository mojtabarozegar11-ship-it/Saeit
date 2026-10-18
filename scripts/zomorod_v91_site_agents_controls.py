"""Print only explicitly selected command control flow. No Django imports."""
import ast,json
from pathlib import Path
root=Path("/home/zomorod2/saeit_v91/zomorodmelal")
paths={
"site_agents":root/"portal/management/commands/run_site_agents.py",
"site_master":root/"portal/management/commands/run_site_master.py",
"permissions":root/"portal/runtime_permissions.py",
}
result={}
for name,p in paths.items():
    source=p.read_text(encoding="utf8")
    tree=ast.parse(source)
    selected=[]
    for n in ast.walk(tree):
        if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name in ("handle","site_agents_launch_allowed"):
            segment=ast.get_source_segment(source,n) or ""
            selected.append({"function":n.name,"code":segment[:6500]})
    result[name]=selected
print(json.dumps({"kind":"V91_COMMAND_CONTROL_FLOW_READ_ONLY","modules":result,"live_db_access":False,"writes":False}))
