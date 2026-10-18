"""Explicit opt-in, strictly private MojPlayWin-main V91 worker activator.

Enables ONLY the private Gen64+review worker. No cPanel cron, no website,
no shared Passenger/Django, no factory and no independent subsite changes.
"""
import json
import os
from pathlib import Path
import stat
import sys

STAGE=Path("/home/zomorod2/.private_mojplaywin_main_agents/v91_verified_main_port_20261018")
CODE=STAGE/"mpw_v91_port"/"worker.py"
STATE=STAGE/"operator_state"
ENABLED=STATE/"enabled"
EXPECTED_FLAG="MPW_V91_MAIN_ONLY_PRIVATE_20261018"

def is_private(p):
    return p.is_dir() and not p.is_symlink() and p.stat().st_mode & 0o077 == 0

def main():
    os.umask(0o077)
    if (not STAGE.is_dir() or STAGE.is_symlink() or not CODE.is_file()
        or CODE.is_symlink() or not is_private(STAGE)):
        raise SystemExit("ABORT_INVALID_PRIVATE_STAGE")
    sys.path.insert(0,str(STAGE))
    from mpw_v91_port.worker import origin_ok, tick
    if not origin_ok():
        raise SystemExit("ABORT_ORIGINAL_77_MODULES_NOT_VERIFIED")
    if STATE.is_symlink():
        raise SystemExit("ABORT_UNSAFE_STATE_SYMLINK")
    STATE.mkdir(mode=0o700,exist_ok=True)
    if not is_private(STATE):
        raise SystemExit("ABORT_UNSAFE_STATE_PERMISSIONS")
    if ENABLED.is_symlink():
        raise SystemExit("ABORT_UNSAFE_ENABLED_FLAG")
    if not ENABLED.exists():
        fd=os.open(str(ENABLED),os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,"w") as output:
            output.write(EXPECTED_FLAG+"\n")
            output.flush();os.fsync(output.fileno())
    if ENABLED.read_text().strip()!=EXPECTED_FLAG:
        raise SystemExit("ABORT_UNKNOWN_ACTIVATION_MARKER")
    status=tick()
    print(json.dumps({"activation":"PRIVATE_MPW_V91_ONLY",
          "result":status["status"],"source_integrity":"verified",
          "main_domain_public_url_live":False,"site_untouched":True,
          "subsites_untouched":True,"factory_untouched":True,
          "automatic_schedule_installed":False},sort_keys=True))
    return 0 if status["status"]=="active_private" else 1

if __name__=="__main__":
    raise SystemExit(main())
