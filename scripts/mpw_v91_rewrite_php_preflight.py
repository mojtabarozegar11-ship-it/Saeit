"""Read-only MojPlayWin root rewrite order, interpreter and collision checks."""
from pathlib import Path
import json,shutil,re,subprocess,os
root=Path("/home/zomorod2/mojplaywin.com")
access=root/".htaccess"
result={"classification":"MOJPLAYWIN_MAIN_AGENTS_FILE_BYPASS_PREFLIGHT","read_only":True}
if not access.is_file() or access.is_symlink():
    result["status"]="MISSING_HTACCESS"
else:
    lines=access.read_text(errors="replace").splitlines()
    records=[]
    for n,line in enumerate(lines,1):
        s=line.strip()
        if s.startswith("#") or not s:continue
        if re.match(r"(?i)^(?:RewriteEngine|RewriteRule|RewriteCond|DirectoryIndex|Options|AddHandler|SetHandler|Passenger(?:App|Enabled|BaseURI|Python)|<IfModule|</IfModule)",s):
            if len(s)>180:continue
            # Only expose rule names and static flags, never rewrite target values or paths.
            parts=s.split()
            record={"line":n,"directive":parts[0]}
            if parts[0].lower()=="rewritecond" and len(parts)>2:
                record.update({"test":parts[1] if parts[1].startswith("%{REQUEST_FILENAME}") else "other",
                               "condition":parts[2] if parts[2] in ("!-f","!-d","-f","-d") else "other"})
            if parts[0].lower()=="rewriterule":
                record["pattern"]=parts[1][:60] if len(parts)>1 else ""
                record["flags"]=parts[-1][:80] if len(parts)>3 and parts[-1].startswith("[") else ""
            records.append(record)
    result["rules"]=records[:80]
    result["php_binary_available"]=bool(shutil.which("php"))
    result["php_version"]=None
    if result["php_binary_available"]:
        try:
            x=subprocess.run(["php","-r","echo PHP_VERSION;"],capture_output=True,text=True,timeout=4)
            result["php_version"]=x.stdout.strip()[:30] if x.returncode==0 else None
        except Exception:pass
    result["static_probe_exists"]=(root/".well-known"/"saeit-static-probe-20261014.txt").exists()
    result["candidate_target_absent"]=not (root/"agents"/"v91"/"index.php").exists()
    result["live_agent_php_path"]=str(root/"agents"/"v91"/"index.php")
    result["file_bypass_proven"]=False
    result["requires_http_canary"]=True
print(json.dumps(result,sort_keys=True))
