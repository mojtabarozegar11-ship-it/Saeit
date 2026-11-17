#!/usr/bin/env python3
"""Read-only MySQL table-size census for the largest cPanel-owned database.

Uses UAPI Mysql::list_databases to select the large schema, and ONLY IF a
preexisting local Unix-socket MariaDB client connection works, reads
information_schema.TABLES metadata. No credentials are requested or exposed.
No SELECT of application data; no SQL writes, DDL or data export.
"""
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import subprocess
import sys
import time

ACCOUNT = "zomorod2"
DBNAME = re.compile(r"^[A-Za-z0-9_]{1,64}$")
LIMIT = 5000


def get_largest_db():
    p = subprocess.run(
        ["uapi", "--output=json", "Mysql", "list_databases"],
        capture_output=True, text=True, timeout=40, check=False,
    )
    if p.returncode:
        raise RuntimeError("UAPI_MYSQL_NOT_AVAILABLE")
    obj = json.loads(p.stdout).get("result", {})
    if not isinstance(obj, dict) or obj.get("status") != 1:
        raise RuntimeError("UAPI_MYSQL_STATUS_BAD")
    databases = obj.get("data")
    if not isinstance(databases, list):
        raise RuntimeError("UAPI_MYSQL_SCHEMA_BAD")
    values = []
    for item in databases:
        if not isinstance(item, dict):
            continue
        name = item.get("database")
        size = item.get("disk_usage")
        if isinstance(size, str) and size.isdigit():
            size = int(size)
        if (not isinstance(name, str) or not DBNAME.fullmatch(name)
                or not isinstance(size, int) or isinstance(size, bool)
                or size < 0):
            continue
        values.append((size, name))
    if not values or len(values) != len(databases):
        raise RuntimeError("INCOMPLETE_DB_SIZE_ROWS")
    values.sort(reverse=True)
    size, name = values[0]
    if size < 10 * 1024**3:
        raise RuntimeError("EXPECTED_LARGE_DATABASE_NOT_FOUND")
    return size, name, len(values)



def verified_local_app_connection(db):
    """Load an existing *local* DB DSN in cPanel memory only; never log it.

    Adapted from the repository's existing
    mojplaywin_consistent_db_preflight_readonly.py / backup stream source.
    """
    import urllib.parse
    root = Path("/home/zomorod2")
    candidates = [
        root/"Saeit-staging/.env",
        root/"Saeit-staging/.env.production",
        root/"Saeit-staging/.env.local",
        root/"mojplaywin.com/.env",
        root/"Saeit/.env",
        root/"Saeit/.env.production",
    ]
    found = set()
    count_matching = 0
    for path in candidates:
        try:
            st = path.lstat()
            import stat
            if (not stat.S_ISREG(st.st_mode) or st.st_uid != os.geteuid()
                    or st.st_size > 65536):
                continue
            source = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line in source.splitlines():
            match = re.match(r"^\s*(?:export\s+)?DATABASE_URL\s*=\s*(.*?)\s*$", line)
            if match is None:
                continue
            raw = match.group(1).strip().strip('"').strip("'")
            try:
                parsed = urllib.parse.urlsplit(raw)
                if parsed.scheme.lower() not in ("mysql", "mariadb", "mysql2"):
                    continue
                actual_db = urllib.parse.unquote(parsed.path.lstrip("/"))
                if actual_db != db:
                    continue
                count_matching += 1
                user = urllib.parse.unquote(parsed.username or "")
                password = urllib.parse.unquote(parsed.password or "")
                host = (parsed.hostname or "localhost").lower()
                port = parsed.port
                if (not user or not password or host not in ("localhost","127.0.0.1")
                        or port not in (None,3306)):
                    continue
                found.add((user,password,host,port))
            except (ValueError,TypeError):
                continue
    if len(found) != 1:
        return None, ("LARGEST_DATABASE_LOCAL_DSN_NOT_FOUND_OR_AMBIGUOUS"
                      if count_matching else "NO_MATCHING_LOCAL_DSN")
    return next(iter(found)), "OK"

def census_table_stats(db):
    exe = shutil.which("mariadb") or shutil.which("mysql")
    if not exe:
        return {"available": False, "reason": "LOCAL_MYSQL_CLIENT_NOT_INSTALLED"}
    verified, reason = verified_local_app_connection(db)
    if verified is None:
        return {"available": False, "reason": reason}
    user, password, host, port = verified
    # Safe quoted name, verified by DBNAME above. No application row data
    # are returned: this query accesses system table statistics only.
    query = (
        "SELECT TABLE_NAME, COALESCE(ENGINE,''), COALESCE(DATA_LENGTH,0), "
        "COALESCE(INDEX_LENGTH,0), COALESCE(DATA_FREE,0), "
        "COALESCE(TABLE_ROWS,0) "
        "FROM information_schema.TABLES "
        "WHERE TABLE_SCHEMA = '" + db + "' "
        "ORDER BY (COALESCE(DATA_LENGTH,0)+COALESCE(INDEX_LENGTH,0)) DESC "
        "LIMIT " + str(LIMIT)
    )
    env = dict(os.environ)
    env["MYSQL_HISTFILE"] = os.devnull
    env["HISTFILE"] = os.devnull
    # Never pass password through argv, output, artifacts or remote SSH.
    env["MYSQL_PWD"] = password
    try:
        p = subprocess.run(
            [exe, "--no-defaults", "--host="+host, "--user="+user,
             "--database="+db, "--connect-timeout=8",
             "--batch", "--raw", "--skip-column-names",
             "--skip-auto-rehash", "--execute", query],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=65,
            env=env,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return {"available": False, "reason": "MYSQL_METADATA_TIMEOUT_OR_EXEC_ERROR"}
    if p.returncode:
        return {"available": False, "reason": "MYSQL_LOCAL_SOCKET_AUTH_OR_SQL_UNAVAILABLE"}
    if len(p.stdout) > 1_000_000:
        return {"available": False, "reason": "METADATA_RESULT_TOO_LARGE"}
    tables = []
    for line in p.stdout.decode("utf-8", errors="replace").splitlines():
        cols = line.split("\t")
        if len(cols) != 6:
            return {"available": False, "reason": "METADATA_BAD_COLUMNS"}
        name, engine, data, index, free, rows = cols
        try:
            data, index, free, rows = map(int, (data, index, free, rows))
        except ValueError:
            return {"available": False, "reason": "METADATA_BAD_NUMBERS"}
        if min(data, index, free, rows) < 0:
            return {"available": False, "reason": "METADATA_NEGATIVE"}
        # Broad size categories only; unknown names are never printed.
        lower = name.casefold()
        category = "other"
        for label, words in (
            ("cache", ("cache", "temp", "tmp")),
            ("sessions", ("session",)),
            ("logs", ("log", "audit", "events")),
            ("archive", ("archive", "history", "old")),
            ("jobs", ("task", "jobs", "queue")),
        ):
            if any(word in lower for word in words):
                category = label
                break
        tables.append({
            "engine": engine if engine in ("InnoDB", "MyISAM", "Aria",
                                           "MEMORY", "CSV") else "other",
            "category_hint": category,
            "data_bytes_estimate": data,
            "index_bytes_estimate": index,
            "free_bytes_estimate": free,
            "rows_estimate": rows,
        })
    tables.sort(key=lambda x: x["data_bytes_estimate"]+x["index_bytes_estimate"], reverse=True)
    stats = {}
    for table in tables:
        label = table["category_hint"]
        d = stats.setdefault(label, {"tables": 0, "data_and_index_bytes": 0})
        d["tables"] += 1
        d["data_and_index_bytes"] += table["data_bytes_estimate"] + table["index_bytes_estimate"]
    return {
        "available": bool(tables),
        "reason": "OK" if tables else "NO_VISIBLE_TABLE_METADATA",
        "read_only": True,
        "estimated_table_count": len(tables),
        "truncated": len(tables) >= LIMIT,
        "aggregate_data_index_bytes_estimate": sum(
            x["data_bytes_estimate"]+x["index_bytes_estimate"] for x in tables),
        "largest_ten_ranked_no_names": [
            dict({"rank": rank+1}, **t) for rank,t in enumerate(tables[:10])],
        "category_hints": stats,
        "stats_are_estimates_not_reclaimable_bytes": True,
        "no_application_rows_read": True,
        "no_schema_or_table_names_disclosed": True,
    }


def main():
    if pwd.getpwuid(os.geteuid()).pw_name != ACCOUNT:
        raise RuntimeError("WRONG_CPANEL_ACCOUNT")
    started = time.monotonic()
    size, name, count = get_largest_db()
    table = census_table_stats(name)
    report = {
        "schema": "moj.factory.cpanel.mysql-tables.readonly.v1",
        "largest_database_uapi_bytes": size,
        "databases_count": count,
        "table_metadata": table,
        "read_only": True,
        "safe_to_delete": False,
        "sql_changes": 0,
        "files_created": 0,
        "files_deleted": 0,
        "elapsed_seconds": round(time.monotonic()-started, 2),
    }
    print("MOJ_CPANEL_MYSQL_TABLE_METADATA="+json.dumps(report,sort_keys=True),
          flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("MOJ_CPANEL_MYSQL_TABLE_METADATA_FAILED="+type(exc).__name__+
              ":"+str(exc)[:90],file=sys.stderr,flush=True)
        sys.exit(1)
