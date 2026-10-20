#!/usr/bin/env python3
"""Read-only, bounded production backup-source throughput diagnostic.

Runs on cPanel from GitHub Actions via pinned SSH. Bytes are read ONLY into
memory and discarded locally on cPanel; no SQL, tar, paths, credentials, SQL
errors, or file contents are sent to GitHub or to the VPS.
Never grants backup/restore or publication approval.
"""
import json
import os
import re
import selectors
import signal
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit, unquote

HOME = Path("/home/zomorod2")
APP = HOME / "Saeit-staging"
DOCROOT = HOME / "mojplaywin.com"
MAX_SAMPLE = 4 * 1024 * 1024
MAX_SECONDS = 25
CONFIGS = (APP / ".env", APP / ".env.production", APP / ".env.local", DOCROOT / ".env")


def connection():
    found = []
    for file in CONFIGS:
        try:
            if file.is_symlink() or not file.is_file() or file.stat().st_size > 65536:
                continue
            for line in file.read_text("utf8", errors="replace").splitlines():
                m = re.match(r"^\\s*(?:export\\s+)?DATABASE_URL\\s*=\\s*(.*?)\\s*$", line)
                if m:
                    p = urlsplit(m.group(1).strip().strip('"').strip("'"))
                    if p.scheme.lower() not in ("mysql", "mariadb", "mysql2"):
                        raise RuntimeError("source_database_scheme")
                    found.append(p)
        except OSError:
            pass
    if len(found) != 1:
        raise RuntimeError("source_database_ambiguous")
    p = found[0]
    db, user, password = unquote(p.path.lstrip("/")), unquote(p.username or ""), unquote(p.password or "")
    if not db or not user or not password or not p.hostname:
        raise RuntimeError("source_database_invalid")
    return p, db, user, password


def command_for(mode):
    if mode == "files":
        if not all(p.is_dir() and not p.is_symlink() for p in (HOME, APP, DOCROOT)):
            raise RuntimeError("source_file_roots_unverified")
        if not shutil.which("tar"):
            raise RuntimeError("source_tar_unavailable")
        return ["nice", "-n", "15", "tar", "-C", str(HOME), "-cf", "-", APP.name, DOCROOT.name], None
    if mode != "mysql":
        raise RuntimeError("unsupported_mode")
    p, db, user, password = connection()
    if not shutil.which("mariadb") or not shutil.which("mariadb-dump"):
        raise RuntimeError("source_dump_unavailable")
    q = subprocess.run(["uapi", "--output=json", "Mysql", "list_databases"], stdout=subprocess.PIPE,
                       stderr=subprocess.DEVNULL, timeout=15, check=False)
    if q.returncode or len(q.stdout) > 300000:
        raise RuntimeError("source_database_listing_unverified")
    response = json.loads(q.stdout).get("result", {})
    rows = response.get("data")
    if response.get("status") != 1 or not isinstance(rows, list) or len(rows) != 1 or rows[0].get("database") != db:
        raise RuntimeError("source_database_mismatch")
    env = dict(os.environ, MYSQL_PWD=password)
    common = ["--host=" + p.hostname, "--user=" + user]
    if p.port is not None:
        common.append("--port=" + str(p.port))
    check = subprocess.run(["mariadb", "--no-defaults", "--batch", "--skip-column-names", *common,
        "--database=" + db, "--connect-timeout=8", "--execute=SELECT COUNT(*), COALESCE(SUM(ENGINE <> 'InnoDB'),0) FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_TYPE='BASE TABLE'"],
        env=env, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=15, check=False)
    try:
        count, other = [int(x) for x in check.stdout.decode("ascii").strip().split()]
    except (ValueError, UnicodeError):
        raise RuntimeError("source_engine_probe_failed") from None
    if check.returncode or count < 1 or other:
        raise RuntimeError("source_nontransactional_or_missing_tables")
    return ["nice", "-n", "15", "mariadb-dump", "--no-defaults", "--single-transaction", "--quick",
        "--skip-lock-tables", "--default-character-set=utf8mb4", "--hex-blob",
        "--routines", "--triggers", "--events", *common, "--databases", db], env


def sample(command, env=None, *, ceiling=MAX_SAMPLE, seconds=MAX_SECONDS):
    """Never return or persist source bytes. Terminate the entire subprocess group."""
    if not (0 < ceiling <= MAX_SAMPLE and 0 < seconds <= MAX_SECONDS):
        raise ValueError("unbounded_probe")
    start = time.monotonic()
    p = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                         env=env, start_new_session=True, bufsize=0)
    count = 0
    selector = selectors.DefaultSelector()
    try:
        selector.register(p.stdout, selectors.EVENT_READ)
        while count < ceiling and time.monotonic() - start < seconds:
            ready = selector.select(timeout=min(0.5, seconds - (time.monotonic() - start)))
            if not ready:
                continue
            b = os.read(p.stdout.fileno(), min(65536, ceiling - count))
            if not b:
                break
            count += len(b)
    finally:
        selector.close()
        try:
            os.killpg(p.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        p.wait(timeout=5)
        p.stdout.close()
    elapsed = max(0.001, time.monotonic() - start)
    return {"classification": "V3_SOURCE_LOCAL_BOUNDED_DISCARD",
            "sample_bytes_discarded_locally": count,
            "sample_limit_reached": count == ceiling,
            "elapsed_seconds": round(elapsed, 2),
            "sample_bytes_per_second": round(count / elapsed),
            "source_bytes_sent_over_ssh": 0,
            "backup_created": False, "release_permitted": False}


def main():
    if len(sys.argv) != 2:
        raise RuntimeError("invalid_mode")
    mode = sys.argv[1]
    if mode == "fixture":
        import tempfile
        with tempfile.TemporaryDirectory() as temp:
            dummy = [sys.executable, "-c", "import sys;sys.stdout.buffer.write(b'x'*262144)"]
            probe = sample(dummy, ceiling=131072, seconds=5)
            assert probe["sample_bytes_discarded_locally"] == 131072
            assert probe["sample_limit_reached"] and not probe["release_permitted"]
        print("V3_LOCAL_DISCARD_FIXTURE=PASS")
        return
    if mode not in ("mysql", "files"):
        raise RuntimeError("invalid_mode")
    result = sample(*command_for(mode))
    result["mode"] = mode
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Exception text may contain filesystem or SQL details, never print it.
        print('V3_SOURCE_LOCAL_BOUNDED_PROBE_FAILED', file=sys.stderr)
        raise SystemExit(1)
