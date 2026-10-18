"""Read-only webroot and routing safety audit before MojPlayWin Gen64 deployment.

No code import, no process signals, no write, no credentials or customer files.
"""
from pathlib import Path
import json, re, os, stat, hashlib
ROOT=Path("/home/zomorod2/mojplaywin.com")
SHARED=Path("/home/zomorod2/Saeit-staging")
PRIVATE=Path("/home/zomorod2/.private_mojplaywin_main_agents/v91_verified_main_port_20261018")
prefixes=("agents","v91","mojtaba.roozegar","picm","studio.Roham","saman","zahra$$","farnaz","taniya")
result={"classification":"MOJPLAYWIN_V91_LIVE_RELEASE_ROUTE_PREFLIGHT",
        "production_deployment_authorized":False,"read_only":True}
def safe_path_info(p):
    if not p.exists() and not p.is_symlink():
        return {"status":"absent"}
    if p.is_symlink():
        return {"status":"symlink_no_follow"}
    try:
        st=p.lstat()
        return {"status":"dir" if stat.S_ISDIR(st.st_mode) else "file" if stat.S_ISREG(st.st_mode) else "other",
                "mode":oct(stat.S_IMODE(st.st_mode))}
    except OSError:
        return {"status":"error"}
result["root"]=safe_path_info(ROOT)
result["private_agent_stage"]=safe_path_info(PRIVATE)
result["root_children"]={k:safe_path_info(ROOT/k) for k in prefixes}
result["candidate_static_endpoint"]=safe_path_info(ROOT/"agents"/"v91")
result["candidate_php_endpoint"]=safe_path_info(ROOT/"agents"/"v91"/"index.php")
result["candidate_cgi_endpoint"]=safe_path_info(ROOT/"agents"/"v91"/"index.cgi")
result["passenger_app"]=safe_path_info(ROOT/"passenger_wsgi.py")
result["shared_python_app"]=safe_path_info(SHARED/"passenger_wsgi.py")
for label,p in (("htaccess",ROOT/".htaccess"),("shared_urlconf",SHARED/"config"/"urls.py")):
    if not p.is_file() or p.is_symlink() or p.stat().st_size>1000000:
        result[label]={"status":"not_readable"}
        continue
    s=p.read_text(encoding="utf-8",errors="replace")
    patterns={
        "passenger":bool(re.search(r"Passenger(?:App|Python|Enabled|BaseURI)",s,re.I)),
        "rewrites_present":bool(re.search(r"(?im)^\s*Rewrite(?:Engine|Rule|Cond)",s)),
        "rewrites_agents":bool(re.search(r"agents/|agents\\b",s,re.I)),
        "rewrite_to_wsgi":bool(re.search(r"passenger|wsgi",s,re.I)),
        "excluded_subsite_prefixes":[x for x in prefixes[2:] if re.search(re.escape(x),s,re.I)],
    }
    result[label]={"status":"read_ok","sha256_prefix":hashlib.sha256(s.encode()).hexdigest()[:16],**patterns}
result["safe_isolated_live_route_proven"]=False
result["shared_passenger_restart_permitted"]=False
result["backup_restore_verified"]=False
print(json.dumps(result,sort_keys=True))
