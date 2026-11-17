#!/usr/bin/env python3
"""Safe quota root census for the Zomorod cPanel account.

Read-only, bounded IO, no file content, no secret paths, no deletion.
Only approved generic top-level folder names can be printed; names of
unexpected entries are SHA-256 pseudonyms to avoid public Actions log leaks.
"""
import hashlib
import json
import os
from pathlib import Path
import pwd
import stat
import subprocess
import sys
import time

EXPECTED_USER = "zomorod2"
KNOWN_DIRS = {
    ".backups", ".cache", ".cpanel", ".config", ".git", ".local",
    ".softaculous", ".trash", "Saeit", "Saeit-staging", "backup",
    "cache", "etc", "logs", "mail", "node_modules", "private",
    "public_ftp", "public_html", "restore-staging", "ssl", "tmp",
    "venv", "virtualenv", "virtualenvs",
}
MIB = 1024 * 1024


def quota_fields():
    try:
        p = subprocess.run(
            ["uapi", "--output=json", "Quota", "get_quota_info"],
            capture_output=True, text=True, timeout=35, check=False,
        )
        if p.returncode:
            return {"available": False}
        result = json.loads(p.stdout).get("result", {})
        data = result.get("data") if isinstance(result, dict) else None
        if not isinstance(data, dict):
            return {"available": False}
        values = {}
        for field in ("megabyte_limit", "megabytes_used", "megabytes_remain",
                      "inode_limit", "inodes_used"):
            val = data.get(field)
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                values[field] = val
        return {"available": bool(values), "values": values}
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return {"available": False}


def label_for(path):
    name = path.name
    if name in KNOWN_DIRS:
        return {"category": "known_account_entry", "name": name}
    # Pseudonym only. Never include raw path, email addresses, hidden names,
    # account tokens, configuration paths or directory contents in logs.
    return {"category": "other_account_entry",
            "entry_id": hashlib.sha256(os.fsencode(name)).hexdigest()[:14],
            "starts_with_dot": name.startswith(".")}


def parse_census(data, root):
    root_b = os.fsencode(str(root))
    rows = []
    total = None
    # GNU du emits tab-delimited allocation records; decoded bytes preserve
    # non-UTF8 filenames for hashing without printing them.
    for raw in data.split(b"\n"):
        if not raw:
            continue
        number, delim, path = raw.partition(b"\t")
        if not delim or not number.isdigit():
            raise RuntimeError("DU_MALFORMED_OUTPUT")
        kib = int(number)
        if path == root_b:
            total = kib * 1024
            continue
        parent = os.path.dirname(path)
        if parent != root_b:
            raise RuntimeError("DU_UNEXPECTED_PARENT")
        filename = os.fsdecode(os.path.basename(path))
        label = label_for(Path(filename))
        rows.append(dict(label, allocated_bytes=kib * 1024))
        if len(rows) > 2500:
            raise RuntimeError("TOO_MANY_TOP_LEVEL_ENTRIES")
    if total is None:
        raise RuntimeError("DU_ROOT_TOTAL_MISSING")
    rows.sort(key=lambda x: x["allocated_bytes"], reverse=True)
    return total, rows


def main():
    ident = pwd.getpwuid(os.geteuid())
    if ident.pw_name != EXPECTED_USER:
        raise RuntimeError("WRONG_ACCOUNT")
    root = Path(ident.pw_dir)
    st = root.lstat()
    if not stat.S_ISDIR(st.st_mode) or root.is_symlink():
        raise RuntimeError("UNSAFE_HOME")
    started = time.monotonic()
    before = quota_fields()
    cmd = ["nice", "-n", "19", "du", "-k", "-x", "-d", "1", str(root)]
    try:
        p = subprocess.run(cmd, stdout=subprocess.PIPE,
                           stderr=subprocess.DEVNULL, check=False,
                           timeout=360)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("ROOT_CENSUS_TIMEOUT") from exc
    if p.returncode:
        raise RuntimeError("ROOT_CENSUS_DU_INCOMPLETE")
    allocated, entries = parse_census(p.stdout, root)
    after = quota_fields()
    if not before["available"] or not after["available"]:
        raise RuntimeError("QUOTA_UAPI_UNAVAILABLE")
    # A hostname-wide df figure is NOT cPanel account quota; only UAPI is.
    pre = before["values"]
    post = after["values"]
    if (pre.get("megabyte_limit") != post.get("megabyte_limit")
            or post.get("megabytes_remain", 0) < 0):
        raise RuntimeError("QUOTA_CHANGED_OR_BAD")
    top = entries[:30]
    classified = {}
    for row in entries:
        key = row.get("name", "other_account_entries")
        classified[key] = classified.get(key, 0) + row["allocated_bytes"]
    report = {
        "schema": "moj.factory.cpanel.account-root-census.v1",
        "readonly": True,
        "account_quota_before": pre,
        "account_quota_after": post,
        "home_allocated_bytes_du": allocated,
        "top_level_entries": len(entries),
        "top30_allocated_bytes": sum(x["allocated_bytes"] for x in top),
        "top30_pseudonymized": top,
        "known_and_other_totals_bytes": classified,
        "du_vs_quota_accounting_may_differ": True,
        "elapsed_seconds": round(time.monotonic() - started, 2),
        "files_deleted": 0,
        "files_created": 0,
        "sensitive_names_in_report": False,
        "safe_to_delete": False,
    }
    print("MOJ_CPANEL_ROOT_CENSUS=" + json.dumps(report, sort_keys=True),
          flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("MOJ_CPANEL_ROOT_CENSUS_FAILED=" + type(exc).__name__ + ":" +
              str(exc)[:100], file=sys.stderr, flush=True)
        sys.exit(1)
