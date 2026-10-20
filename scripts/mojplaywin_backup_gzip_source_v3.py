#!/usr/bin/env python3
"""MojPlayWin v3: gzip the scoped backup on cPanel BEFORE pinned-SSH transport.

Only outputs a single gzip member followed by the fixed completion marker.
This script does not write to the hosting filesystem, import SQL, restart apps,
traverse unknown sites, or read any tenant outside the existing two main roots.
On failure it must NEVER append the marker. No sensitive stderr output.
"""
from __future__ import annotations

import io
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
from urllib.parse import unquote, urlsplit
import zlib

HOME = Path("/home/zomorod2")
APP = HOME / "Saeit-staging"
DOCROOT = HOME / "mojplaywin.com"
MARKER = b"\n-- MJWP-RECOVERY-20261017-COMPLETE-F91D7C40 --\n"
MAX_RAW_BYTES = 12 * 1024 ** 3
MAX_COMPRESSED_BYTES = 12 * 1024 ** 3
BLOCK = 128 * 1024


def connection():
    urls = []
    for path in (APP / ".env", APP / ".env.production", APP / ".env.local", DOCROOT / ".env"):
        try:
            if path.is_symlink() or not path.is_file() or path.stat().st_size > 65536:
                continue
            for line in path.read_text("utf8", errors="replace").splitlines():
                m = re.match(r"^\s*(?:export\s+)?DATABASE_URL\s*=\s*(.*?)\s*$", line)
                if m:
                    url = urlsplit(m.group(1).strip().strip('"').strip("'"))
                    if url.scheme.lower() not in ("mysql", "mariadb", "mysql2"):
                        raise RuntimeError("wrong_database_scheme")
                    urls.append(url)
        except OSError:
            continue
    if len(urls) != 1:
        raise RuntimeError("ambiguous_database_configuration")
    url = urls[0]
    db = unquote(url.path.lstrip("/"))
    user = unquote(url.username or "")
    password = unquote(url.password or "")
    if not all((db, user, password, url.hostname)):
        raise RuntimeError("invalid_database_configuration")
    return url, db, user, password


def database_matches(db):
    result = subprocess.run(["uapi", "--output=json", "Mysql", "list_databases"],
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                            timeout=15, check=False)
    if result.returncode or len(result.stdout) > 300000:
        return False
    data = json.loads(result.stdout).get("result", {})
    rows = data.get("data")
    return data.get("status") == 1 and isinstance(rows, list) and len(rows) == 1 and rows[0].get("database") == db


def mysql_command():
    url, db, user, password = connection()
    if not database_matches(db) or not shutil.which("mariadb") or not shutil.which("mariadb-dump"):
        raise RuntimeError("mysql_backup_prerequisites_failed")
    env = dict(os.environ, MYSQL_PWD=password)
    opts = ["--host=" + url.hostname, "--user=" + user]
    if url.port is not None:
        opts += ["--port=" + str(url.port)]
    verify = subprocess.run([
        "mariadb", "--no-defaults", "--batch", "--skip-column-names", *opts,
        "--database=" + db, "--connect-timeout=8",
        "--execute=SELECT COUNT(*), COALESCE(SUM(ENGINE <> 'InnoDB'),0) FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_TYPE='BASE TABLE'"
    ], env=env, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=15, check=False)
    try:
        count, nontransactional = map(int, verify.stdout.decode("ascii").split())
    except (UnicodeError, ValueError):
        raise RuntimeError("mysql_engine_probe_invalid") from None
    if verify.returncode or count < 1 or nontransactional != 0:
        raise RuntimeError("mysql_transactional_snapshot_not_proven")
    command = [
        "nice", "-n", "15", "mariadb-dump", "--no-defaults", "--single-transaction",
        "--quick", "--skip-lock-tables", "--default-character-set=utf8mb4",
        "--hex-blob", "--routines", "--triggers", "--events", *opts, "--databases", db,
    ]
    return command, env


def files_command():
    if any(p.is_symlink() or not p.is_dir() for p in (HOME, APP, DOCROOT)):
        raise RuntimeError("main_site_root_unverified")
    if not shutil.which("tar"):
        raise RuntimeError("tar_unavailable")
    return ["nice", "-n", "15", "tar", "-C", str(HOME), "-cf", "-", APP.name, DOCROOT.name], None


def compress_process(command, *, env=None, out=None, max_raw=MAX_RAW_BYTES):
    """Bounded constant-memory compressor; completion marker iff child exited zero."""
    if not 0 < max_raw <= MAX_RAW_BYTES:
        raise ValueError("unbounded_source")
    out = sys.stdout.buffer if out is None else out
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                               env=env, bufsize=0, start_new_session=True)
    gz = zlib.compressobj(level=1, wbits=31)
    raw_size = 0
    wire_size = 0
    try:
        assert process.stdout is not None
        while True:
            chunk = process.stdout.read(BLOCK)
            if not chunk:
                break
            raw_size += len(chunk)
            if raw_size > max_raw:
                raise RuntimeError("source_size_limit")
            encoded = gz.compress(chunk)
            if encoded:
                wire_size += len(encoded)
                if wire_size > MAX_COMPRESSED_BYTES:
                    raise RuntimeError("encoded_size_limit")
                out.write(encoded)
        if process.wait(timeout=45) != 0 or raw_size < 1024:
            raise RuntimeError("source_process_failed")
        trailer = gz.flush(zlib.Z_FINISH)
        wire_size += len(trailer)
        if wire_size > MAX_COMPRESSED_BYTES:
            raise RuntimeError("encoded_size_limit")
        out.write(trailer)
        out.write(MARKER)
        out.flush()
        return {"raw_bytes": raw_size, "gzip_bytes": wire_size,
                "encoding": "gzip-with-footer-v1", "source_complete": True}
    finally:
        if process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
        if process.stdout is not None:
            process.stdout.close()


def fixture():
    # Small fixture avoids the command-line argument size limit on Linux.
    script = "import sys;sys.stdout.buffer.write(b'V3 synthetic gzip test\\n'*20000)"
    target = io.BytesIO()
    r = compress_process([sys.executable, "-c", script], out=target)
    binary = target.getvalue()
    assert binary.endswith(MARKER)
    assert zlib.decompress(binary[:-len(MARKER)], wbits=31) == b"V3 synthetic gzip test\n" * 20000
    assert r["source_complete"] and r["gzip_bytes"] < r["raw_bytes"]
    print("V3_SOURCE_GZIP_FIXTURE=PASS")


if __name__ == "__main__":
    try:
        if len(sys.argv) != 2:
            raise RuntimeError("mode_required")
        if sys.argv[1] == "fixture":
            fixture()
        elif sys.argv[1] in ("mysql", "files"):
            mode = sys.argv[1]
            command, env = mysql_command() if mode == "mysql" else files_command()
            report = compress_process(command, env=env)
            # Only aggregate measurements to stderr; stdout stays binary.
            print(json.dumps({"classification": "V3_SOURCE_GZIP_VERIFIED",
                              "mode": mode, "source_complete": report["source_complete"],
                              "raw_bytes": report["raw_bytes"],
                              "compressed_bytes": report["gzip_bytes"],
                              "production_written": False}, sort_keys=True), file=sys.stderr)
        else:
            raise RuntimeError("unknown_mode")
    except Exception:
        print("V3_SOURCE_GZIP_INCOMPLETE_NO_RELEASE", file=sys.stderr)
        raise SystemExit(1)
