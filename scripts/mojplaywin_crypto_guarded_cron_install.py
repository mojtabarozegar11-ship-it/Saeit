#!/usr/bin/env python3
"""Install one isolated, idempotent MojPlayWin-only cron entry.

Never print, edit or delete another site's task. An immutable backup of the
prior full crontab is written with 0600 permissions outside public webroots.
The on-server reconciliation command has a feature flag and is inert while off.
"""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys

PRIVATE=Path("/home/zomorod2/.mojplaywin-crypto-payments-v1")
PHP_SCRIPT=Path("/home/zomorod2/mojplaywin.com/checkout/crypto/index.php")
MARKER="MOJPLAYWIN_CRYPTO_RECONCILE_V1"


def run(args, input_data=None):
    return subprocess.run(args, input=input_data, text=True, capture_output=True, timeout=15)


def main(identifier):
    if not identifier.isdigit() or not 1 <= len(identifier) <= 20:
        raise RuntimeError("Invalid deployment run id.")
    if not PRIVATE.is_dir() or PRIVATE.is_symlink() or not PHP_SCRIPT.is_file() or PHP_SCRIPT.is_symlink():
        raise RuntimeError("Isolated payment runtime is not installed.")
    if (PRIVATE/"enabled.flag").exists() or (PRIVATE/"enabled.flag").is_symlink():
        raise RuntimeError("Cron must be installed before enabling actual payments.")
    exe=shutil.which("crontab")
    php=shutil.which("php")
    if not exe or not php or not Path(php).is_file():
        raise RuntimeError("Required local scheduler or PHP interpreter unavailable.")
    old=run([exe,"-l"])
    if old.returncode:
        message=old.stderr.lower()
        if "no crontab for" in message and old.returncode==1:
            before=""
        else:
            raise RuntimeError("Existing cron could not be read safely.")
    else:
        before=old.stdout
    line=f"*/3 * * * * {php} {PHP_SCRIPT} reconcile >/dev/null 2>&1 # {MARKER}"
    entries=[v for v in before.splitlines() if MARKER in v]
    if entries:
        if len(entries)!=1 or entries[0]!=line:
            raise RuntimeError("Conflicting pre-existing MojPlayWin payment schedule.")
        print("MOJPLAYWIN_AUTORECONCILE_ALREADY_SCHEDULED=true")
        return
    backup=PRIVATE/("prior-crontab-"+identifier+".txt")
    if backup.exists() or backup.is_symlink():
        raise RuntimeError("Cron backup destination must be new.")
    fd=os.open(str(backup),os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,"O_NOFOLLOW",0),0o600)
    with os.fdopen(fd,"w",encoding="utf-8") as fh:
        fh.write(before)
        fh.flush()
        os.fsync(fh.fileno())
    # Check for concurrent changes before replacing the operator's full cron.
    current=run([exe,"-l"])
    if current.returncode==0:
        now=current.stdout
    elif current.returncode==1 and "no crontab for" in current.stderr.lower():
        now=""
    else:
        raise RuntimeError("Cannot verify the current cron without changes.")
    if now!=before:
        raise RuntimeError("Concurrent cron edit detected; original unchanged.")
    new=before.rstrip("\n")+"\n"+line+"\n"
    result=run([exe,"-"],new)
    if result.returncode!=0:
        raise RuntimeError("Scheduler rejected the MojPlayWin-only additional cron line.")
    verify=run([exe,"-l"])
    if verify.returncode or verify.stdout!=new:
        raise RuntimeError("Installed crontab differs from reviewed content; examine private backup.")
    print("MOJPLAYWIN_AUTORECONCILE_SCHEDULED_EVERY_3_MIN=true")
    print("MOJPLAYWIN_PREEXISTING_CRON_LINES_PRESERVED=true")
    print("MOJPLAYWIN_PRIOR_CRON_BACKUP_PRIVATE=true")
    print("MOJPLAYWIN_PRODUCTION_PAYMENTS_ENABLED=false")


if __name__=="__main__":
    if len(sys.argv)!=2:
        raise SystemExit("Provide deployment run ID.")
    main(sys.argv[1])
