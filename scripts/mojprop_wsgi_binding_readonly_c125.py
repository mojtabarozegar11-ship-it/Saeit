#!/usr/bin/env python3
"""Read-only AST/metadata inspection of the two fixed MojProp/MojPlayWin WSGI entrypoints."""
from __future__ import annotations
import ast
import json
import os
import stat
from pathlib import Path

OWNER = "zomorod2"
HOME = Path("/home/zomorod2")
CANDIDATES = {
    "mojprop_app_root_wsgi": HOME / "Saeit-mojprop-candidate-20261122" / "passenger_wsgi.py",
    "legacy_mojplaywin_wsgi": HOME / "mojplaywin.com" / "passenger_wsgi.py",
}

def size_band(n):
    if n == 0: return "0"
    if n <= 4096: return "1-4KB"
    if n <= 16384: return "4-16KB"
    return ">16KB"

def inspect(path):
    out = {
        "exists": False, "regular": False, "symlink": False,
        "owner_verified": False, "size_band": "unknown",
        "parseable_python": False, "assignment_names": [],
        "safe_home_path_literals": [], "import_modules": [],
        "has_sys_path_insert": False, "has_os_chdir": False,
        "has_get_wsgi_application": False,
    }
    try:
        meta = path.lstat()
        out["exists"] = True
        out["regular"] = stat.S_ISREG(meta.st_mode)
        out["symlink"] = stat.S_ISLNK(meta.st_mode)
        out["owner_verified"] = meta.st_uid == os.geteuid() and pwd_name() == OWNER
        out["size_band"] = size_band(meta.st_size)
        if not out["regular"] or out["symlink"] or meta.st_nlink != 1:
            return out
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        out["parseable_python"] = True
        names, paths, imports = set(), set(), set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        names.add(target.id[:64])
                if isinstance(node.value, ast.Constant) and type(node.value.value) is str:
                    value = node.value.value
                    if value.startswith(str(HOME) + "/") and ".." not in Path(value).parts:
                        paths.add(value[:512])
            elif isinstance(node, ast.Import):
                imports.update(alias.name[:96] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module[:96])
            elif isinstance(node, ast.Call):
                fn = node.func
                if (isinstance(fn, ast.Attribute) and fn.attr == "insert"
                    and isinstance(fn.value, ast.Attribute)
                    and fn.value.attr == "path"
                    and isinstance(fn.value.value, ast.Name)
                    and fn.value.value.id == "sys"):
                    out["has_sys_path_insert"] = True
                if (isinstance(fn, ast.Attribute) and fn.attr == "chdir"
                    and isinstance(fn.value, ast.Name) and fn.value.id == "os"):
                    out["has_os_chdir"] = True
                if isinstance(fn, ast.Name) and fn.id == "get_wsgi_application":
                    out["has_get_wsgi_application"] = True
        out["assignment_names"] = sorted(names)[:40]
        out["safe_home_path_literals"] = sorted(paths)[:20]
        out["import_modules"] = sorted(imports)[:40]
    except (OSError, UnicodeError, SyntaxError, ValueError):
        pass
    return out

def pwd_name():
    import pwd
    try: return pwd.getpwuid(os.geteuid()).pw_name
    except (KeyError, OSError): return ""

def main():
    try:
        owner_ok = pwd_name() == OWNER
    except Exception:
        owner_ok = False
    report = {
        "schema": "mojprop.wsgi.binding.readonly.c125.v1",
        "read_only": True,
        "owner_verified": owner_ok,
        "files": {key: inspect(path) for key, path in CANDIDATES.items()},
        "files_modified": False, "service_restarted": False,
        "database_accessed": False, "customer_data_accessed": False,
        "payment_created": False, "email_sent": False,
        "deployment_authorized": False, "cost_incurred": False,
    }
    print("MOJPROP_C125_WSGI_BINDING=" + json.dumps(report, sort_keys=True, separators=(",", ":")))

if __name__ == "__main__":
    main()
