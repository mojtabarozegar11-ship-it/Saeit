#!/usr/bin/env python3
"""Only fixed, public source file inode metadata on owner's cPanel; no writes."""
import getpass, json, stat
from pathlib import Path

ROOT = Path("/home/zomorod2")
STATIC = ("public_html/index.html","public_html/company/index.html",
          "public_html/services/index.html","public_html/en/partners/index.html",
          "public_html/privacy/index.html","public_html/b2b/index.html",
    "public_html/b2b/privacy/index.html")
SOURCES = ("Saeit-staging/config/urls.py","Saeit-staging/core/company_sales_views.py",
           "Saeit-staging/passenger_wsgi.py","Saeit/config/urls.py",
           "Saeit/core/company_sales_views.py","Saeit/passenger_wsgi.py")

def state(root, path):
    if not root.is_absolute() or root.is_symlink() or ".." in Path(path).parts:
        return "unsafe"
    current=root
    for part in Path(path).parts:
        current=current/part
        try: m=current.lstat()
        except FileNotFoundError: return "missing"
        except (OSError,PermissionError): return "unavailable"
        if stat.S_ISLNK(m.st_mode): return "unsafe"
        if current != root/path and not stat.S_ISDIR(m.st_mode): return "unsafe"
    if not stat.S_ISREG(m.st_mode) or m.st_mode & 0o002: return "unsafe"
    return "present"

def inventory(root=ROOT, verify=True):
    if verify and (root != ROOT or getpass.getuser() != "zomorod2"):
        raise PermissionError("Wrong owner")
    if not root.is_dir() or root.is_symlink():
        raise FileNotFoundError("Missing owner directory")
    public={p:state(root,p) for p in STATIC}
    return {"schema":"zomorod.b2b.readonly_source_inventory.v1",
            "read_only":True,"owner_verified":bool(verify),
            "public_static":public,
            "django_source_candidates":{p:state(root,p) for p in SOURCES},
            "possible_static_company_shadow":public["public_html/company/index.html"]=="present",
            "database_read":False,"customer_data_read":False,
            "file_content_read":False,"site_changed":False,
            "backup_verified":False,"release_performed":False,
            "passenger_route_verified":False,"http_verified":False}

if __name__=="__main__":
    print("ZOMOROD_B2B_READONLY="+json.dumps(inventory(),sort_keys=True,separators=(",",":")))
