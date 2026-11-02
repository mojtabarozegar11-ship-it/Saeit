#!/usr/bin/env python3
"""Read-only, redacted diagnosis of the public MojPlayWin Passenger registration.

Never prints raw uapi records, process command lines, paths from other sites,
environment variables, SQL, credentials, application source or customer data.
No restart, edits, migrations, connection to a database, or service mutation.
"""
from __future__ import annotations

import hashlib
import json
import os
import pwd
import re
import shutil
import subprocess
import sys
from pathlib import Path

PUBLIC = Path("/home/zomorod2/mojplaywin.com")
APP = Path("/home/zomorod2/Saeit-staging")
KNOWN_GUEST_SHA = "7693254e4ed72141b6de7fc283c5a3214159ea49d838318337e47e86953f5f2f"


def _as_target_root(value):
    """Classify only two allowlisted roots; never return the original string."""
    if not isinstance(value, str):
        return "unknown"
    value = value.strip().strip("'\"").rstrip("/")
    if value in (str(PUBLIC), "mojplaywin.com"):
        return "public"
    if value in (str(APP), "Saeit-staging"):
        return "staging"
    return "other"


def _uapi_summary(payload):
    if not isinstance(payload, dict):
        return {"ok": False, "public_root": False, "staging_root": False,
                "mentions_domain": False}
    result = payload.get("result")
    if not isinstance(result, dict):
        return {"ok": False, "public_root": False, "staging_root": False,
                "mentions_domain": False}
    ok = result.get("status") == 1 or result.get("status") is True
    strings = []
    def walk(item, depth=0):
        if depth > 8 or len(strings) >= 500:
            return
        if isinstance(item, str):
            strings.append(item)
        elif isinstance(item, dict):
            for key, value in list(item.items())[:50]:
                if isinstance(key, str) and key.lower() in (
                        "app_path", "application_root", "path", "document_root",
                        "domain", "domain_name", "name", "app_root", "base_uri",
                        "url", "app_name", "directory"):
                    walk(value, depth + 1)
                elif isinstance(value, (dict, list)):
                    walk(value, depth + 1)
        elif isinstance(item, list):
            for value in item[:100]:
                walk(value, depth + 1)
    walk(result.get("data"))
    return {"ok": bool(ok),
            "public_root": any(_as_target_root(s) == "public" for s in strings),
            "staging_root": any(_as_target_root(s) == "staging" for s in strings),
            "mentions_domain": any(s.lower().strip() in
                                   ("mojplaywin.com", "www.mojplaywin.com")
                                   for s in strings)}


def _run_uapi():
    if shutil.which("uapi") is None:
        return None
    try:
        completed = subprocess.run(
            ["uapi", "--output=json", "PassengerApps", "list_applications"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            timeout=35, check=False)
        if completed.returncode or len(completed.stdout) > 2_000_000:
            return None
        return json.loads(completed.stdout)
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return None


def _passenger_status_summary(raw=None):
    """Parse Passenger app roots without disclosing other apps or raw status."""
    available = True
    readable = False
    if raw is None:
        executable = shutil.which("passenger-status")
        available = executable is not None
        if executable is None:
            return {"available": False, "readable": False,
                    "public_root": False, "staging_root": False}
        try:
            command = subprocess.run([executable], stdout=subprocess.PIPE,
                                     stderr=subprocess.DEVNULL, timeout=25,
                                     check=False)
            if command.returncode or len(command.stdout) > 2_000_000:
                return {"available": True, "readable": False,
                        "public_root": False, "staging_root": False}
            raw = command.stdout
        except (OSError, subprocess.TimeoutExpired):
            return {"available": True, "readable": False,
                    "public_root": False, "staging_root": False}
    if not isinstance(raw, (bytes, str)) or len(raw) > 2_000_000:
        return {"available": available, "readable": False,
                "public_root": False, "staging_root": False}
    body = raw.decode("utf-8", "replace") if isinstance(raw, bytes) else raw
    roots = re.findall(r"(?im)^\\s*App root:\\s*([^\\r\\n]+)", body)
    readable = bool(roots or "Application groups" in body)
    return {"available": available, "readable": readable,
            "public_root": any(_as_target_root(v) == "public" for v in roots),
            "staging_root": any(_as_target_root(v) == "staging" for v in roots)}


def _owned_workers():
    """Only aggregate this user's candidate Python/Passenger processes."""
    result = {"candidate_count": 0, "cwd_public": 0, "cwd_staging": 0}
    procs = Path("/proc")
    if not procs.is_dir():
        return result
    uid = os.geteuid()
    try:
        paths = (p for p in procs.iterdir() if p.name.isdigit())
        for path in paths:
            try:
                if path.stat().st_uid != uid:
                    continue
                cmd = (path / "cmdline").read_bytes()[:16384].lower()
                if not any(token in cmd for token in (b"passenger", b"python", b"wsgi")):
                    continue
                result["candidate_count"] += 1
                cwd = Path(os.readlink(path / "cwd"))
                if cwd == PUBLIC or PUBLIC in cwd.parents:
                    result["cwd_public"] += 1
                if cwd == APP or APP in cwd.parents:
                    result["cwd_staging"] += 1
            except (OSError, ValueError):
                continue
    except OSError:
        pass
    return result


def inspect(*, public=PUBLIC, app=APP, uapi_payload=None, workers=None, status_payload=None):
    if public == PUBLIC and app == APP and pwd.getpwuid(os.geteuid()).pw_name != "zomorod2":
        raise RuntimeError("WRONG_CPANEL_ACCOUNT")
    if public.is_symlink() or app.is_symlink() or not public.is_dir() or not app.is_dir():
        raise RuntimeError("WRONG_PUBLIC_APP_ROOTS")
    htaccess = public / ".htaccess"
    wsgi = public / "passenger_wsgi.py"
    guest = app / "services/mpw_trx_guest_commerce.py"
    marker = public / "tmp/restart.txt"
    conf = htaccess.read_text("utf-8", "replace") if htaccess.is_file() and not htaccess.is_symlink() else ""
    roots = re.findall(r"(?im)^\s*PassengerAppRoot\s+([^\r\n#]+)", conf)
    wsgi_text = wsgi.read_text("utf-8", "replace") if wsgi.is_file() and not wsgi.is_symlink() else ""
    guest_prior = bool(guest.is_file() and not guest.is_symlink() and
                       hashlib.sha256(guest.read_bytes()).hexdigest() == KNOWN_GUEST_SHA)
    marker_ok = marker.is_file() and not marker.is_symlink()
    guest_ok = guest.is_file() and not guest.is_symlink()
    if uapi_payload is None:
        uapi_payload = _run_uapi()
    api = _uapi_summary(uapi_payload)
    status = _passenger_status_summary(status_payload)
    if workers is None:
        workers = _owned_workers()
    return {"classification": "MPW_PUBLIC_PASSENGER_READ_ONLY_RUNTIME_CONTRACT",
            "public_app_root_directive_count": len(roots),
            "htaccess_public_root": len(roots) == 1 and _as_target_root(roots[0]) == "public",
            "htaccess_staging_root": len(roots) == 1 and _as_target_root(roots[0]) == "staging",
            "public_wsgi_references_staging": str(APP) in wsgi_text,
            "guest_module_restored_to_known_prior": guest_prior,
            "public_restart_marker_present": bool(marker_ok),
            "public_restart_marker_newer_than_guest": bool(
                marker_ok and guest_ok and marker.stat().st_mtime >= guest.stat().st_mtime),
            "uapi_passenger_list_ok": api["ok"],
            "uapi_registers_public_root": api["public_root"],
            "uapi_registers_staging_root": api["staging_root"],
            "uapi_mentions_public_domain": api["mentions_domain"],
            "passenger_status_cli_available": status["available"],
            "passenger_status_registry_readable": status["readable"],
            "passenger_status_public_root": status["public_root"],
            "passenger_status_staging_root": status["staging_root"],
            "owned_candidate_worker_count_capped": min(100, workers["candidate_count"]),
            "owned_worker_cwd_public_count_capped": min(100, workers["cwd_public"]),
            "owned_worker_cwd_staging_count_capped": min(100, workers["cwd_staging"]),
            "python_minor": sys.version_info.minor,
            "production_service_restarted": False,
            "effective_public_worker_proven": False,
            "database_or_customer_data_read": False,
            "files_modified": False,
            "release_permitted": False}


if __name__ == "__main__":
    if sys.argv[1:] != ["inspect"]:
        raise SystemExit(2)
    try:
        report = inspect()
    except Exception:
        print("MPW_PASSENGER_DIAGNOSTIC=PREREQUISITE_REJECTED", file=sys.stderr)
        raise SystemExit(1)
    print(json.dumps(report, sort_keys=True))
