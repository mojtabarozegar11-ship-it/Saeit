#!/usr/bin/env python3
"""One owner-scoped Passenger template reload signal, preserving all code and configuration."""
import os,pwd,stat,sys,time,json
from pathlib import Path
APP=Path("/home/zomorod2/Saeit-staging")
MARKER=APP/"tmp/restart.txt"
if pwd.getpwuid(os.getuid()).pw_name!="zomorod2":raise RuntimeError("WRONG_OWNER")
if os.environ.get("ATELIER_OWNER_PASSENGER_TEMPLATE_RELOAD")!="owner-879-20261021":
    raise PermissionError("NOT_OWNER_APPROVED")
if APP.is_symlink() or not (APP/"passenger_wsgi.py").is_file() or not MARKER.is_file() or MARKER.is_symlink():
    raise RuntimeError("WRONG_OR_MISSING_PASSENGER_APP_MARKER")
before=MARKER.stat()
if not stat.S_ISREG(before.st_mode) or before.st_uid!=os.getuid():raise RuntimeError("UNTRUSTED_PASSENGER_MARKER")
MARKER.touch(exist_ok=True)
after=MARKER.stat()
if after.st_mtime_ns < before.st_mtime_ns:raise RuntimeError("RESTART_SIGNAL_TIMESTAMP_REGRESSED")
print("ATELIER_PASSENGER_TEMPLATE_RELOAD_SIGNAL="+json.dumps({"exact_app":str(APP),"existing_marker_touched":True,"no_config_changes":True,"no_files_deleted":True},sort_keys=True))
