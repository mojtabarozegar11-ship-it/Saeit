#!/usr/bin/env python3
"""ONE-TIME authorized production backup stream: MySQL or two main filesystem roots.

Runs on cPanel via pinned SSH and sends raw bytes ONLY over stdout through SSH.
NO source-side archive, temporary dump, log of DB credentials, site code change,
mysqldump lock, Django import, deploy, Passenger restart or write operation.
This is NOT an inventory or backup of unidentified independent tenant paths.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit, unquote

HOME = Path("/home/zomorod2")
APP = HOME / "Saeit-staging"
DOCROOT = HOME / "mojplaywin.com"
MARKER = b"\n-- MJWP-RECOVERY-20261017-COMPLETE-F91D7C40 --\n"
MAX_STREAM = 12 * 1024**3


def load_connection():
    urls = []
    for p in (APP / ".env", APP / ".env.production", APP / ".env.local", DOCROOT / ".env"):
        try:
            if p.is_symlink() or not p.is_file() or p.stat().st_size > 65536:
                continue
            for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
                m = re.match(r"^\s*(?:export\s+)?DATABASE_URL\s*=\s*(.*?)\s*$", line)
                if m:
                    parsed = urlsplit(m.group(1).strip().strip('"').strip("'"))
                    if parsed.scheme.lower() not in ("mysql", "mariadb", "mysql2"):
                        raise RuntimeError("wrong database backend")
                    urls.append(parsed)
        except OSError:
            continue
    if len(urls) != 1:
        raise RuntimeError("unverified number of database configurations")
    p = urls[0]
    db, user, password = unquote(p.path.lstrip("/")), unquote(p.username or ""), unquote(p.password or "")
    if not db or not user or not password:
        raise RuntimeError("invalid database configuration")
    return p, db, user, password


def database_matches(db):
    q = subprocess.run(["uapi", "--output=json", "Mysql", "list_databases"],
                       stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=15)
    if q.returncode or len(q.stdout) > 300000:
        return False
    result = json.loads(q.stdout).get("result", {})
    data = result.get("data")
    return result.get("status") == 1 and isinstance(data, list) and len(data) == 1 and data[0].get("database") == db


def base_cmd(p, db, user):
    cmd = ["mariadb", "--no-defaults", "--batch", "--skip-column-names",
           "--host="+(p.hostname or "localhost"), "--user="+user,
           "--database="+db, "--connect-timeout=8"]
    if p.port is not None:
        cmd.append("--port="+str(p.port))
    return cmd


def copy_exact_process_stdout(command, *, env=None):
    proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                            env=env, bufsize=0)
    total = 0
    try:
        assert proc.stdout is not None
        while True:
            b = proc.stdout.read(65536)
            if not b:
                break
            total += len(b)
            if total > MAX_STREAM:
                raise RuntimeError("source stream exceeds safety cap")
            sys.stdout.buffer.write(b)
        if proc.wait(timeout=30):
            raise RuntimeError("source archive or transactional DB dump failed")
        sys.stdout.buffer.write(MARKER)
        sys.stdout.buffer.flush()
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()


def stream_mysql():
    p, db, user, password = load_connection()
    if not database_matches(db) or not shutil.which("mariadb-dump"):
        raise RuntimeError("source DB not verified or dump client missing")
    env = dict(os.environ, MYSQL_PWD=password)
    args = base_cmd(p, db, user)
    engines = subprocess.run(args + ["--execute=SELECT COUNT(*), COALESCE(SUM(ENGINE <> 'InnoDB'),0) FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_TYPE='BASE TABLE'"],
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                             env=env, timeout=15)
    if engines.returncode:
        raise RuntimeError("could not verify transactional tables")
    try:
        fields = engines.stdout.decode("ascii").strip().split()
        if len(fields) != 2 or int(fields[0]) < 1 or int(fields[1]) != 0:
            raise RuntimeError("nontransactional/unknown database table engine")
    except (UnicodeError, ValueError) as exc:
        raise RuntimeError("could not parse DB engine totals") from exc
    cmd = ["nice", "-n", "15", "mariadb-dump", "--no-defaults", "--single-transaction",
           "--quick", "--skip-lock-tables", "--default-character-set=utf8mb4",
           "--hex-blob", "--routines", "--triggers", "--events",
           "--host="+(p.hostname or "localhost"), "--user="+user]
    if p.port is not None:
        cmd.append("--port="+str(p.port))
    cmd.extend(["--databases", db])
    copy_exact_process_stdout(cmd, env=env)


def stream_files():
    for p in (APP, DOCROOT):
        if p.is_symlink() or not p.is_dir():
            raise RuntimeError("missing main site source folder")
    if not shutil.which("tar"):
        raise RuntimeError("tar unavailable")
    # Paths are relative to one fixed hosting account. GNU tar preserves links
    # as link entries; does NOT silently follow them to unapproved other sites.
    cmd = ["nice", "-n", "15", "tar", "-C", str(HOME), "-cf", "-",
           APP.name, DOCROOT.name]
    copy_exact_process_stdout(cmd)


if __name__ == "__main__":
    try:
        if len(sys.argv) != 2 or sys.argv[1] not in ("mysql", "files"):
            raise RuntimeError("unsupported source mode")
        if sys.argv[1] == "mysql":
            stream_mysql()
        else:
            stream_files()
    except Exception:
        # Never log database names, source URLs, errors containing secrets,
        # tar filenames or customer contents.
        print("SOURCE_BACKUP_STREAM_FAILED_NO_RELEASE", file=sys.stderr)
        raise SystemExit(1)
