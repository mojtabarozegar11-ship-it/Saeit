#!/usr/bin/env python3
"""Read-only bounded inspection of known MojPlayWin GET-only dynamic shell."""
import os, json, hashlib, re
from pathlib import Path
home=Path("/home/zomorod2")
root=home/"mojplaywin.com"
file=root/"design-preview-20261017"/"_mpw_dynamic_main_shell_20261019.php"
for p in (root,root/"design-preview-20261017",file):
    o={"path":str(p),"exists":p.exists(),"symlink":p.is_symlink()}
    if p.exists() and not p.is_symlink():
        st=p.stat()
        o.update(uid=st.st_uid,bytes=st.st_size,mode=oct(st.st_mode & 0o777),file=p.is_file())
    print("SHELL_IDENTITY",json.dumps(o))
if file.is_symlink() or not file.is_file() or file.stat().st_size>250000:
    raise SystemExit("FAIL_CLOSED_INVALID_SHELL")
b=file.read_bytes()
print("SHELL_SHA256",hashlib.sha256(b).hexdigest())
s=b.decode("utf-8","replace")
lines=s.splitlines()
print("SHELL_LINES",len(lines))
patterns=("games","products","first realm","digital products","__mpw_template_route","</main>","<main","ob_start","ob_get","preg_replace","str_replace","htmlspecialchars","header(","curl_","file_get_contents","echo ","function ","include ","require ")
indices={i for i,line in enumerate(lines) if any(p in line.lower() for p in patterns)}
expanded=set()
for i in indices:
    for j in range(max(0,i-2),min(len(lines),i+3)):expanded.add(j)
if len(expanded)>260:
    expanded={i for i in expanded if i<300}
def safe(t):
    if any(w in t.lower() for w in ("secret","password","private_key","access_token","api_key","client_secret","authorization:","credential","passwd")):
        return "[REDACTED]"
    return t[:360]
for i in sorted(expanded):
    print("SHELL_SOURCE",json.dumps({"line":i+1,"text":safe(lines[i])},ensure_ascii=False))
for needle in ("First Realm","Digital Products","__mpw_template_route","<main","</main>","arcade-lab"):
    print("SHELL_MARKER",json.dumps({"marker":needle,"count":s.lower().count(needle.lower()),"positions":[m.start() for m in list(re.finditer(re.escape(needle),s,re.I))[:8]]}))
