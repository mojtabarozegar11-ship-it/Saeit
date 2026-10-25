#!/usr/bin/env python3
"""Set a one-minute, single-locked and capacity-guarded owner-VPS leech author cadence.

Runs only on the owner's VPS through its authenticated SSH deployment relay.
Preserves all unrelated cron entries, all sites, and every manuscript segment.
"""
import os
from pathlib import Path
import subprocess

MARKER = "saeit-private-leech-vps-selfhosted-author-20261025"
AUTHOR = Path("/home/githubops/factory-runtime/operations/production-instructions/leech-vps-resource-guarded-author.py")
TARGET = "* * * * * /usr/bin/python3 -B " + str(AUTHOR) + " >/dev/null 2>&1 # " + MARKER
OLD = "*/10 * * * * /usr/bin/python3 -B " + str(AUTHOR) + " >/dev/null 2>&1 # " + MARKER
if os.geteuid() == 0:
    raise SystemExit("REFUSE_ROOT_CRONTAB")
if subprocess.run(["id", "-un"], capture_output=True, text=True, check=True).stdout.strip() != "githubops":
    raise SystemExit("OWNER_ONLY")
if AUTHOR.is_symlink() or not AUTHOR.is_file():
    raise SystemExit("OWNER_AUTHOR_NOT_READY")
read = subprocess.run(["crontab", "-l"], capture_output=True, text=True, timeout=8)
if read.returncode != 0:
    raise SystemExit("CRONTAB_UNAVAILABLE")
rows = read.stdout.splitlines()
owned = [i for i, row in enumerate(rows) if MARKER in row]
if len(owned) != 1 or rows[owned[0]] not in (OLD, TARGET):
    raise SystemExit("OWNED_SINGLE_CRON_ENTRY_MISMATCH")
if rows[owned[0]] != TARGET:
    rows[owned[0]] = TARGET
    subprocess.run(["crontab", "-"], input="\n".join(rows) + "\n",
                   text=True, check=True, timeout=8)
verify = subprocess.run(["crontab", "-l"], capture_output=True,
                        text=True, check=True, timeout=8).stdout.splitlines()
if verify != rows:
    raise SystemExit("CRON_POSTWRITE_READBACK_MISMATCH")
print("LEECH_OWNER_VPS_ONE_MINUTE_SINGLE_LOCKED_CADENCE=installed")
print("LEECH_PREEXISTING_UNRELATED_CRON_ENTRIES=preserved")
