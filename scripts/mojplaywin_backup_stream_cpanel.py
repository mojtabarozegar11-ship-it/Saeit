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
    return (result.get("status") == 1 and isinstance(data, list)
            and len(data) <= 1000
            and sum(1 for row in data if isinstance(row, dict)
                    and row.get("database") == db) == 1)


def base_cmd(p, db, user):
    cmd = ["mariadb", "--no-defaults", "--batch", "--skip-column-names",
           "--host="+(p.hostname or "localhost"), "--user="+user,
           "--database="+db, "--connect-timeout=8"]
    if p.port is not None:
        cmd.append("--port="+str(p.port))
    return cmd


def copy_exact_process_stdout(command, *, env=None, verify_after=None):
    proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                            env=env, bufsize=0)
    total = 0
    progress_mib = 0
    try:
        assert proc.stdout is not None
        while True:
            b = proc.stdout.read(65536)
            if not b:
                break
            total += len(b)
            if total > MAX_STREAM:
                raise RuntimeError("source stream exceeds safety cap")
            if total == len(b):
                print("BACKUP_SOURCE_STREAM_STARTED", file=sys.stderr, flush=True)
            current_mib = (total // (64 * 1024 * 1024)) * 64
            if current_mib > progress_mib:
                progress_mib = current_mib
                print(f"BACKUP_SOURCE_PROGRESS_MIB={progress_mib}", file=sys.stderr, flush=True)
            sys.stdout.buffer.write(b)
        if proc.wait(timeout=30):
            raise RuntimeError("source archive or transactional DB dump failed")
        if verify_after is not None:
            verify_after()  # Before trusted footer; failing streams cannot be accepted.
        sys.stdout.buffer.write(MARKER)
        sys.stdout.buffer.flush()
        print("BACKUP_SOURCE_STREAM_COMPLETED", file=sys.stderr, flush=True)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()



def mysql_account_inventory_summary(db):
    """Aggregate-only cPanel database-list diagnostic; never log database names."""
    report = {
        "classification": "MYSQL_ACCOUNT_INVENTORY_READ_ONLY",
        "uapi_executed": True, "response_wellformed": False,
        "result_status_ok": False, "database_list_is_array": False,
        "listed_database_count_capped": 0, "expected_exact_matches": 0,
    }
    try:
        q = subprocess.run(
            ["uapi", "--output=json", "Mysql", "list_databases"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=15,
        )
        if q.returncode or len(q.stdout) > 300000:
            return report
        document = json.loads(q.stdout)
        result = document.get("result", {})
        rows = result.get("data")
        report["response_wellformed"] = True
        report["result_status_ok"] = result.get("status") == 1
        report["database_list_is_array"] = isinstance(rows, list)
        if isinstance(rows, list):
            report["listed_database_count_capped"] = min(len(rows), 1000)
            report["expected_exact_matches"] = sum(
                1 for row in rows if isinstance(row, dict) and row.get("database") == db)
    except Exception:
        pass
    return report


def preflight_mysql_source():
    """Bounded source-only SELECT. Errors use fixed codes, never secret values."""
    try:
        p, db, user, password = load_connection()
    except Exception:
        raise RuntimeError("MYSQL_SOURCE_CONFIG_UNVERIFIED") from None
    try:
        account_match = database_matches(db)
    except Exception:
        account_match = False
    if not account_match:
        print("MPW_MYSQL_ACCOUNT_INVENTORY=" +
              json.dumps(mysql_account_inventory_summary(db), sort_keys=True),
              file=sys.stderr)
        raise RuntimeError("MYSQL_ACCOUNT_DB_UNVERIFIED")
    if not shutil.which("mariadb") or not shutil.which("mariadb-dump"):
        raise RuntimeError("MYSQL_CLIENT_UNAVAILABLE")
    env = dict(os.environ, MYSQL_PWD=password)
    query = ("SELECT DATABASE(), COUNT(*), "
             "COALESCE(SUM(ENGINE <> 'InnoDB'),0) FROM information_schema.TABLES "
             "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_TYPE='BASE TABLE'")
    try:
        result = subprocess.run(
            base_cmd(p, db, user) + ["--execute=" + query],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=env, timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise RuntimeError("MYSQL_SOURCE_SELECT_UNAVAILABLE") from None
    if result.returncode or len(result.stdout) > 1024:
        raise RuntimeError("MYSQL_SOURCE_SELECT_UNAVAILABLE")
    try:
        fields = result.stdout.decode("ascii").strip().split()
        if len(fields) != 3:
            raise RuntimeError("MYSQL_SOURCE_SELECT_UNEXPECTED")
        if fields[0] != db:
            raise RuntimeError("MYSQL_SESSION_DB_MISMATCH")
        if int(fields[1]) < 1 or int(fields[2]) != 0:
            raise RuntimeError("MYSQL_TABLE_ENGINE_UNSAFE")
    except (UnicodeError, ValueError):
        raise RuntimeError("MYSQL_SOURCE_SELECT_UNEXPECTED") from None
    return {
        "classification": "MYSQL_BACKUP_SOURCE_CLI_READ_ONLY",
        "configured_and_session_database_match": True,
        "all_tables_transactional": True,
        "dump_executed": False,
        "orders_created": 0,
        "payments_created": 0,
        "passenger_effective_database_proven": False,
        "release_permitted": False,
    }


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



def assert_no_unbacked_symlinks(roots=(APP, DOCROOT), max_entries=200_000):
    """Reject a misleading 'complete' file archive with external dependencies.

    Pure metadata check: no file content read, no link followed during walk,
    and no private path or link target included in any error.
    """
    for root in roots:
        if root.is_symlink() or not root.is_dir():
            raise RuntimeError("UNSAFE_PRIMARY_BACKUP_ROOT")
    roots = tuple(root.resolve() for root in roots)
    entries = links = 0

    def onerror(_error):
        raise RuntimeError("BACKUP_LINK_SCAN_INCOMPLETE")

    for root in roots:
        for directory, dirs, files in os.walk(
                root, followlinks=False, onerror=onerror):
            entries += len(dirs) + len(files)
            if entries > max_entries:
                raise RuntimeError("BACKUP_LINK_SCAN_LIMIT")
            for entry in dirs + files:
                path = Path(directory) / entry
                if not path.is_symlink():
                    continue
                links += 1
                try:
                    destination = path.resolve(strict=True)
                except (OSError, RuntimeError):
                    raise RuntimeError("BACKUP_LINK_UNRESOLVABLE") from None
                if not any(destination == allowed or allowed in destination.parents
                           for allowed in roots):
                    raise RuntimeError("BACKUP_LINK_OUTSIDE_APPROVED_ROOTS")
    return {"checked_entries": entries, "symlinks_inside_roots": links}


def sidecar_equals_plain_local_only(compressed, plain, max_plain=2 * 1024**2):
    """Bounded local byte equivalence. No names or content leave cPanel.

    A nonstandard compressed sidecar is never trusted just by extension or
    small size; decompressed bytes must equal the already-scoped ordinary file.
    """
    import gzip
    import zlib

    try:
        plain_size = plain.stat().st_size
        if (plain_size < 0 or plain_size > max_plain or
                compressed.stat().st_size > 256 * 1024):
            return False
        codec = compressed.suffix.casefold()
        if codec == ".gz":
            with gzip.open(compressed, "rb") as decoder, plain.open("rb") as source:
                counted = 0
                while True:
                    chunk = decoder.read(65536)
                    if not chunk:
                        break
                    counted += len(chunk)
                    if counted > max_plain or source.read(len(chunk)) != chunk:
                        return False
                return counted == plain_size and not source.read(1)
        if codec != ".br":
            return False
        brotli_bin = shutil.which("brotli")
        if not brotli_bin:
            return False
        with compressed.open("rb") as encoded, plain.open("rb") as source:
            proc = subprocess.Popen([brotli_bin, "-d", "-c"], stdin=encoded,
                                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            try:
                counted = 0
                assert proc.stdout is not None
                while True:
                    chunk = proc.stdout.read(65536)
                    if not chunk:
                        break
                    counted += len(chunk)
                    if counted > max_plain or source.read(len(chunk)) != chunk:
                        return False
                return (counted == plain_size and not source.read(1) and
                        proc.wait(timeout=10) == 0)
            finally:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait()
    except (OSError, EOFError, ValueError, zlib.error, subprocess.TimeoutExpired):
        return False


def assert_scoped_public_asset_links(roots=(APP, DOCROOT), home=HOME,
                                     max_entries=200_000, max_asset_entries=100_000,
                                     max_asset_bytes=512 * 1024**2):
    """Dry-run-only guard for a future site-scoped, self-contained file snapshot.

    ONLY docroot's direct public static/assets/uploads aliases are eligible.
    Their linked content must be same-account-owned, bounded, ordinary files
    and directories; neither parent projects nor unlinked siblings are read.
    No contents, private target paths or credentials are logged.
    This function itself does not create or transfer an archive.
    """
    import stat

    if len(roots) != 2:
        raise RuntimeError("BACKUP_PRIMARY_ROOT_COUNT")
    app_root, public_root = tuple(Path(p) for p in roots)
    for root in (app_root, public_root):
        if root.is_symlink() or not root.is_dir() or root.resolve() != root:
            raise RuntimeError("UNSAFE_PRIMARY_BACKUP_ROOT")
    account = Path(home).resolve(strict=True)
    expected = frozenset(("static", "assets", "uploads"))
    seen = {}
    source_parents = {}
    count = 0

    def walk_error(_error):
        raise RuntimeError("BACKUP_LINK_SCAN_INCOMPLETE")

    for root in (app_root, public_root):
        for dirname, dirs, files in os.walk(
                root, followlinks=False, onerror=walk_error):
            count += len(dirs) + len(files)
            if count > max_entries:
                raise RuntimeError("BACKUP_LINK_SCAN_LIMIT")
            for entry in dirs + files:
                path = Path(dirname) / entry
                info = path.lstat()
                if not stat.S_ISLNK(info.st_mode):
                    if not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):
                        raise RuntimeError("BACKUP_PRIMARY_SPECIAL_FILE")
                    continue
                if entry not in expected:
                    raise RuntimeError("UNKNOWN_PUBLIC_ALIAS")
                if (entry == "static" and path.parent != public_root or
                        entry in ("assets", "uploads") and path.parent.parent != public_root):
                    raise RuntimeError("UNEXPECTED_ASSET_ALIAS_DEPTH")
                if info.st_uid != os.geteuid():
                    raise RuntimeError("PUBLIC_ALIAS_OWNER_MISMATCH")
                if entry in seen:
                    raise RuntimeError("DUPLICATE_PUBLIC_ALIAS")
                try:
                    target = path.resolve(strict=True)
                except (OSError, RuntimeError):
                    raise RuntimeError("ASSET_LINK_UNRESOLVABLE") from None
                if (target == account or account not in target.parents or
                        not target.is_dir() or target.stat().st_uid != os.geteuid()):
                    raise RuntimeError("ASSET_LINK_TARGET_OUT_OF_SCOPE")
                seen[entry] = target
                source_parents[entry] = path.parent
    if frozenset(seen) != expected:
        raise RuntimeError("REQUIRED_PUBLIC_ASSET_ALIAS_MISSING")
    if source_parents["assets"] != source_parents["uploads"]:
        raise RuntimeError("NESTED_ASSET_PARENT_MISMATCH")

    result = {}
    unpaired_compressed_count = 0
    for label in sorted(expected):
        target = seen[label]
        entries = regular_bytes = 0
        def target_error(_error):
            raise RuntimeError("ASSET_TREE_UNREADABLE")
        for dirname, dirs, files in os.walk(
                target, followlinks=False, onerror=target_error):
            entries += len(dirs) + len(files)
            if entries > max_asset_entries:
                raise RuntimeError("ASSET_TREE_ENTRY_LIMIT")
            for entry in dirs + files:
                item = Path(dirname) / entry
                info = item.lstat()
                if (entry.startswith(".") or
                        info.st_uid != os.geteuid() or
                        stat.S_ISLNK(info.st_mode)):
                    raise RuntimeError("ASSET_TREE_UNAPPROVED_MEMBER")
                if stat.S_ISREG(info.st_mode):
                    name = entry.casefold()
                    suffix = item.suffix.casefold()
                    if (name in (".env", "id_rsa", "wp-config.php", "secrets.yml") or
                            suffix in (".pem", ".key", ".p12", ".pfx",
                                       ".sql", ".sqlite", ".sqlite3", ".db",
                                       ".bak", ".gpg", ".age")):
                        raise RuntimeError("ASSET_TREE_SENSITIVE_FILE_SHAPE")
                    if suffix in (".zip", ".tar", ".7z"):
                        raise RuntimeError("ASSET_TREE_ARCHIVE_FILE_SHAPE")
                    if suffix in (".gz", ".br"):
                        source = item.with_suffix("")
                        allowed = {".css", ".js", ".mjs", ".html", ".svg",
                                   ".woff", ".woff2", ".ttf", ".otf", ".ico", ".map",
                                   ".png", ".jpg", ".jpeg", ".gif", ".webp",
                                   ".avif", ".pdf", ".mp3", ".mp4", ".webm",
                                   ".wav", ".ogg", ".json", ".xml", ".txt",
                                   ".md", ".csv", ".webmanifest", ".wasm"}
                        # Never accept sensitive, archive, source-code,
                        # symlinked, directory or other-owned base files.
                        forbidden_base_types = {
                            ".pem", ".key", ".p12", ".pfx", ".sql", ".sqlite",
                            ".sqlite3", ".db", ".bak", ".gpg", ".age", ".zip",
                            ".tar", ".7z", ".py", ".php", ".sh", ".rb",
                            ".go", ".java", ".jsx", ".tsx", ".ts", ".vue",
                            ".yml", ".yaml", ".toml",
                        }
                        if (source.is_symlink() or
                                (source.exists() and not source.is_file()) or
                                source.suffix.casefold() in forbidden_base_types):
                            raise RuntimeError("ASSET_COMPRESSED_SIDECAR_UNVERIFIED")
                        if source.is_file():
                            if source.stat().st_uid != os.geteuid():
                                raise RuntimeError("ASSET_COMPRESSED_SIDECAR_UNVERIFIED")
                            if (source.suffix.casefold() not in allowed and
                                    not sidecar_equals_plain_local_only(item, source)):
                                raise RuntimeError("ASSET_COMPRESSED_SIDECAR_UNVERIFIED")
                        else:
                            if source.suffix.casefold() not in allowed:
                                raise RuntimeError("ASSET_COMPRESSED_SIDECAR_UNVERIFIED")
                            # Only conventional missing-base sidecars remain
                            # subject to the two-file, 256-KiB exception.
                            unpaired_compressed_count += 1
                            if (unpaired_compressed_count > 2 or
                                    info.st_size > 256 * 1024):
                                raise RuntimeError("ASSET_COMPRESSED_SIDECAR_UNVERIFIED")
                    regular_bytes += info.st_size
                elif not stat.S_ISDIR(info.st_mode):
                    raise RuntimeError("ASSET_TREE_SPECIAL_FILE")
                if regular_bytes > max_asset_bytes:
                    raise RuntimeError("ASSET_TREE_BYTE_LIMIT")
        info = target.stat()
        result[label] = (info.st_dev, info.st_ino, entries, regular_bytes)
    return result


def stream_files():
    for p in (APP, DOCROOT):
        if p.is_symlink() or not p.is_dir():
            raise RuntimeError("missing main site source folder")
    if not shutil.which("tar"):
        raise RuntimeError("tar unavailable")
    # This entire-tree preflight rejects every link except the three
    # pinned public aliases. Only the contents reachable from those aliases
    # are copied; unrelated parent projects and siblings are never traversed.
    snapshot = assert_scoped_public_asset_links()
    def verify_after():
        if assert_scoped_public_asset_links() != snapshot:
            raise RuntimeError("SCOPED_PUBLIC_ASSET_DRIFT_DURING_BACKUP")
    # -h makes all three aliases ordinary archive subdirectories, so isolated
    # restoration never needs access to other account roots.
    cmd = ["nice", "-n", "15"] + scoped_files_tar_command()
    copy_exact_process_stdout(cmd, verify_after=verify_after)


def scoped_files_tar_command(home=HOME, roots=(APP, DOCROOT)):
    """Exact TAR argv for a standalone archive; use only after scoped guard."""
    return ["tar", "--dereference", "-C", str(home), "-cf", "-",
            roots[0].name, roots[1].name]


if __name__ == "__main__":
    try:
        if len(sys.argv) != 2 or sys.argv[1] not in ("mysql", "files", "preflight-scoped-files", "preflight-mysql"):
            raise RuntimeError("unsupported source mode")
        if sys.argv[1] == "mysql":
            stream_mysql()
        elif sys.argv[1] == "preflight-mysql":
            print("MPW_MYSQL_BACKUP_PREFLIGHT=" +
                  json.dumps(preflight_mysql_source(), sort_keys=True))
        elif sys.argv[1] == "preflight-scoped-files":
            summary = assert_scoped_public_asset_links()
            print("MPW_SCOPED_ASSET_PREFLIGHT=" + json.dumps({
                "classification": "READ_ONLY_SELF_CONTAINED_BACKUP_PREP",
                "approved_public_aliases": sorted(summary),
                "public_alias_count": len(summary),
                "target_entry_counts": {key: val[2] for key, val in summary.items()},
                "only_bounded_sidecar_equality_bytes_read_locally": True,
                "no_content_or_private_names_logged": True,
                "source_modified": False,
                "archive_started": False,
                "release_permitted": False,
            }, sort_keys=True))
        else:
            stream_files()
    except Exception as exc:
        # Only hard-coded categories. Never echo arbitrary exceptions, paths,
        # DB credentials, target names or customer data into CI logs.
        safe_codes = {
            "BACKUP_PRIMARY_ROOT_COUNT", "UNSAFE_PRIMARY_BACKUP_ROOT",
            "BACKUP_LINK_SCAN_INCOMPLETE", "BACKUP_LINK_SCAN_LIMIT",
            "BACKUP_PRIMARY_SPECIAL_FILE", "UNSCOPED_PRIMARY_SYMLINK",
            "NESTED_PUBLIC_ASSET_SYMLINK", "UNKNOWN_PUBLIC_ALIAS",
            "PUBLIC_ALIAS_OWNER_MISMATCH", "DUPLICATE_PUBLIC_ALIAS",
            "UNEXPECTED_ASSET_ALIAS_DEPTH", "NESTED_ASSET_PARENT_MISMATCH",
            "ASSET_LINK_UNRESOLVABLE", "ASSET_LINK_TARGET_OUT_OF_SCOPE",
            "REQUIRED_PUBLIC_ASSET_ALIAS_MISSING", "ASSET_TREE_UNREADABLE",
            "ASSET_TREE_ENTRY_LIMIT", "ASSET_TREE_UNAPPROVED_MEMBER",
            "ASSET_TREE_UNAPPROVED_FILE_SHAPE", "ASSET_TREE_SPECIAL_FILE",
            "ASSET_TREE_BYTE_LIMIT", "ASSET_TREE_SENSITIVE_FILE_SHAPE",
            "ASSET_TREE_ARCHIVE_FILE_SHAPE",
            "ASSET_COMPRESSED_SIDECAR_UNVERIFIED",
        }
        if len(sys.argv) == 2 and sys.argv[1] == "preflight-mysql":
            fixed = {
                "MYSQL_SOURCE_CONFIG_UNVERIFIED", "MYSQL_ACCOUNT_DB_UNVERIFIED",
                "MYSQL_CLIENT_UNAVAILABLE", "MYSQL_SOURCE_SELECT_UNAVAILABLE",
                "MYSQL_SOURCE_SELECT_UNEXPECTED", "MYSQL_SESSION_DB_MISMATCH",
                "MYSQL_TABLE_ENGINE_UNSAFE",
            }
            code = str(exc) if type(exc) is RuntimeError and str(exc) in fixed else "UNCLASSIFIED"
            print("MYSQL_BACKUP_SOURCE_PREFLIGHT_FAILED_NO_RELEASE category=" + code,
                  file=sys.stderr)
        elif len(sys.argv) == 2 and sys.argv[1] == "preflight-scoped-files":
            code = str(exc) if type(exc) is RuntimeError and str(exc) in safe_codes else "unknown"
            print("SCOPED_PUBLIC_ASSET_PREFLIGHT_FAILED_NO_RELEASE category=" + code, file=sys.stderr)
        else:
            print("SOURCE_BACKUP_STREAM_FAILED_NO_RELEASE", file=sys.stderr)
        raise SystemExit(1)
