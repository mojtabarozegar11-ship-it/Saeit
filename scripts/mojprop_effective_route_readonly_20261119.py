"""Bounded read-only MOJ PROP Apache and Passenger route diagnosis.

Fixed paths, no application import, database, process modification, credentials,
environment values or file contents in output. A matching HTTP body is evidence
of the static response, not proof of the identity of a running Python worker.
"""
import ast
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import stat
import sys

PUBLIC = Path("/home/zomorod2/mojplaywin.com")
STAGING = Path("/home/zomorod2/Saeit-staging")
MAX = 512000

def safe_read(root, relative, limit=MAX):
    try:
        root_info = root.lstat()
        if not stat.S_ISDIR(root_info.st_mode) or root_info.st_uid != os.geteuid() or root_info.st_mode & 0o022:
            return None
        target = root / relative
        parent = target.parent
        while parent != root:
            if root not in parent.parents:
                return None
            info = parent.lstat()
            if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o022:
                return None
            parent = parent.parent
        fd = os.open(target, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o022 or info.st_size > limit:
                return None
            data = stream.read(limit+1)
        return data if len(data) <= limit else None
    except (OSError, ValueError):
        return None

def classify_root(value, public, staging):
    value = value.strip().strip("\"'").rstrip("/")
    if value in (str(public), public.name):
        return "public"
    if value in (str(staging), staging.name):
        return "staging"
    return "other_or_dynamic"

def config_signals(data, public, staging):
    if data is None:
        return {"readable": False, "app_root_declarations": [], "prop_rewrite_mentions": 0,
                "directory_index_mentions": 0, "python_declaration_present": False}
    lines = [line.strip() for line in data.decode("utf-8", "replace").splitlines()
             if line.strip() and not line.lstrip().startswith("#")]
    roots = [classify_root(line.split(None, 1)[1], public, staging)
             for line in lines if re.match(r"(?i)^PassengerAppRoot\s+\S", line)]
    return {"readable": True, "app_root_declarations": roots[:8],
            "prop_rewrite_mentions": min(50, sum(bool(re.match(r"(?i)^Rewrite(?:Rule|Cond)\b", line)) and
                                               "moj-prop" in line.lower() for line in lines)),
            "directory_index_mentions": min(20, sum(bool(re.match(r"(?i)^DirectoryIndex\b", line)) for line in lines)),
            "python_declaration_present": any(re.match(r"(?i)^PassengerPython\s+\S", line) for line in lines)}

def entry_signals(data, public, staging):
    out = {"ast_valid": False, "literal_root_public": False, "literal_root_staging": False,
           "django_entrypoint_mentioned": False}
    if data is None:
        return out
    try:
        tree = ast.parse(data.decode("utf-8"))
    except (SyntaxError, UnicodeError, ValueError, RecursionError, MemoryError):
        return out
    values = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and type(n.value) is str]
    out["ast_valid"] = True
    out["literal_root_public"] = str(public) in values
    out["literal_root_staging"] = str(staging) in values
    out["django_entrypoint_mentioned"] = any(isinstance(n, ast.ImportFrom) and
        n.module in ("config.wsgi", "django.core.wsgi") for n in ast.walk(tree))
    return out

def inspect(public, staging, public_sha):
    disk = safe_read(public, "moj-prop/index.html")
    public_config = config_signals(safe_read(public, ".htaccess", 65536), public, staging)
    nested_config = config_signals(safe_read(public, "moj-prop/.htaccess", 65536), public, staging)
    return {"schema": "mojprop.route.effective.readonly.v1", "read_only": True,
            "public_landing_file_readable": disk is not None,
            "public_get_matches_landing_file": disk is not None and hashlib.sha256(disk).hexdigest() == public_sha,
            "public_config": public_config, "prop_config": nested_config,
            "public_entry": entry_signals(safe_read(public, "passenger_wsgi.py", 32768), public, staging),
            "staging_entry": entry_signals(safe_read(staging, "passenger_wsgi.py", 32768), public, staging),
            "source_candidates": {label: {
                "django_settings_present": safe_read(root, "config/settings.py") is not None,
                "django_urls_present": safe_read(root, "config/urls.py") is not None,
                "simulation_engine_present": safe_read(root, "prop_firm/simulation_engine.py") is not None,
            } for label, root in (("public", public), ("staging", staging))},
            "live_worker_identity_proven": False, "database_accessed": False,
            "production_change_authorized": False}

if __name__ == "__main__":
    if (len(sys.argv) != 2 or not re.fullmatch(r"[0-9a-f]{64}", sys.argv[1])
            or os.geteuid() == 0 or pwd.getpwuid(os.geteuid()).pw_name != "zomorod2"):
        raise SystemExit(2)
    print("MOJPROP_ROUTE_READONLY=" + json.dumps(inspect(PUBLIC, STAGING, sys.argv[1]), sort_keys=True))
