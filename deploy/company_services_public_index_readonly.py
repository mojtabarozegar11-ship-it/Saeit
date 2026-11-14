#!/usr/bin/env python3
"""Read-only structural identity of current public /services/ directory on cPanel."""
import hashlib
import os
from pathlib import Path
import pwd
import stat

root=Path.home()/"public_html"/"services"
assert pwd.getpwuid(os.getuid()).pw_name=="zomorod2"
if root.is_symlink() or not root.is_dir() or root.stat().st_uid!=os.getuid():
    print("ZM_SERVICES_ORIGIN=UNSAFE_OR_ABSENT")
    raise SystemExit(1)
print("ZM_SERVICES_ORIGIN_DIRECTORY=verified")
for name in ("index.html","index.php",".htaccess","scope/index.html","scope/AGR-01/index.html"):
    path=root/name
    exists=path.exists() or path.is_symlink()
    print("ZM_SERVICES_ORIGIN_"+name.replace("/","_").replace(".","_").upper()+"_EXISTS="+str(exists).lower())
    if not exists:
        continue
    if path.is_symlink() or not path.is_file():
        print("ZM_SERVICES_ORIGIN_"+name.replace("/","_").replace(".","_").upper()+"_SAFE=false")
        continue
    info=path.stat()
    safe=stat.S_ISREG(info.st_mode) and info.st_uid==os.getuid() and info.st_size<=250_000
    print("ZM_SERVICES_ORIGIN_"+name.replace("/","_").replace(".","_").upper()+"_SAFE="+str(safe).lower())
    if not safe:
        continue
    data=path.read_bytes()
    print("ZM_SERVICES_ORIGIN_"+name.replace("/","_").replace(".","_").upper()+"_SHA256="+hashlib.sha256(data).hexdigest())
    if name in ("index.html","index.php"):
        print("ZM_SERVICES_ORIGIN_"+name.replace(".","_").upper()+"_SIX_SCOPE_LINKS="+str(sum(data.count((f"/services/scope/{c}/").encode("ascii")) for c in ("AGR-01","RS-01","RS-02","RS-03","WEB-01","SEO-01"))))
        print("ZM_SERVICES_ORIGIN_"+name.replace(".","_").upper()+"_OFFER_MARKER="+str(b"service-offers-heading" in data).lower())
print("ZM_SERVICES_ORIGIN_READ_ONLY=true")
