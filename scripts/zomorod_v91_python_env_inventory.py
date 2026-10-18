"""Read-only discover Python interpreters that include Django on cPanel."""
import json,os,stat,subprocess
from pathlib import Path
HOME=Path("/home/zomorod2")
SEARCH=[HOME/"virtualenv",HOME/"saeit_v91"/"zomorodmelal"/".venv"]
candidates=[]
for root in SEARCH:
    if not root.is_dir() or root.is_symlink():continue
    for path,dirs,files in os.walk(root,followlinks=False):
        rel=Path(path).relative_to(root)
        if len(rel.parts)>4:
            dirs[:]=[]
            continue
        dirs[:]=[x for x in dirs if x not in {".git","node_modules","__pycache__"} and not (Path(path)/x).is_symlink()]
        if Path(path).name=="bin":
            for name in ("python","python3","python3.11","python3.9"):
                f=Path(path)/name
                if f.exists() and len(candidates)<20 and os.access(f,os.X_OK):
                    candidates.append(f)
            dirs[:]=[]
res=[]
for c in sorted(set(candidates)):
    try:
        proc=subprocess.run([str(c),"-B","-I","-c",
            "import importlib.util,sys; print(sys.version.split()[0]+' '+str(importlib.util.find_spec('django') is not None))"],
            stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=5,text=True,env={"PYTHONDONTWRITEBYTECODE":"1"})
        first=proc.stdout.strip()[:90] if proc.returncode==0 else "invalid"
    except (OSError,subprocess.TimeoutExpired):
        first="unavailable"
    res.append({"candidate":str(c).replace(str(HOME)+"/","~/"),"result":first})
print(json.dumps({"kind":"V91_CPANEL_DJANGO_INTERPRETERS_READONLY","candidates":res,"checked":len(res),
"site_mutated":False,"db_access_attempted":False},sort_keys=True))
