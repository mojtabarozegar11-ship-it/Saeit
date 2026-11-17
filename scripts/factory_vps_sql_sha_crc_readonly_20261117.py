#!/usr/bin/env python3
"""Read-only SHA-256 and gzip-CRC validation of known Nov 4 SQL segments.

Does NOT read MySQL/SQLite live, export records, restore, delete, write files,
send bytes offhost, or print table names or SQL data. Reads compressed files
locally on VPS and discards decompressed bytes after gzip CRC verification.
Historical fragment integrity cannot prove a current or full database restore.
"""
import gzip
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import stat
import sys
import time

ROOT = Path("/home/githubops/.db-backups/zomorod2_sites_main-segments-20261104")
BASES = ("core_agenttask", "core_factoryevidence")
META_PATTERN = re.compile(
    r"^(core_agenttask|core_factoryevidence)\.(\d+)(?:\.sub(\d+))?\.meta$")
SHA_PATTERN = re.compile(r"^sha256=([0-9a-f]{64})$", re.M)
SIZE_PATTERN = re.compile(r"^compressed_bytes=(\d+)$", re.M)
MAX_FILES = 80
MAX_META = 8192
MAX_COMPRESSED = 600 * 1024**2
MAX_UNCOMPRESSED = 6 * 1024**3
MAX_TOTAL_UNCOMPRESSED = 40 * 1024**3
MAX_SECONDS = 650
BLOCK = 2 * 1024**2

def owned_file(p):
    try:
        s = p.lstat()
    except FileNotFoundError:
        raise RuntimeError("ARCHIVE_FILE_MISSING") from None
    if not stat.S_ISREG(s.st_mode) or s.st_uid != os.geteuid():
        raise RuntimeError("ARCHIVE_FILE_UNSAFE")
    return s

def fingerprint(st):
    return (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)

def ensure_budget(started):
    if time.monotonic() - started >= MAX_SECONDS:
        raise TimeoutError("READ_ONLY_VERIFICATION_BUDGET_EXCEEDED")

def check_payload(p, expected_size, expected_sha, started):
    before = owned_file(p)
    if before.st_size != expected_size or not 0 < before.st_size <= MAX_COMPRESSED:
        return {"result":"SIZE_MISMATCH_OR_BOUND","sha256_ok":False,
                "gzip_crc_ok":False,"content_disclosed":False},0
    digest = hashlib.sha256()
    hashed = 0
    with p.open("rb", buffering=0) as f:
        while True:
            ensure_budget(started)
            part = f.read(BLOCK)
            if not part:
                break
            digest.update(part)
            hashed += len(part)
    digest_ok = hashed == before.st_size and digest.hexdigest() == expected_sha
    uncompressed = 0
    crc_ok = False
    error_type = None
    try:
        with gzip.open(p, "rb") as f:
            while True:
                ensure_budget(started)
                chunk = f.read(BLOCK)
                if not chunk:
                    break
                uncompressed += len(chunk)
                if uncompressed > MAX_UNCOMPRESSED:
                    raise ValueError("SEGMENT_DECOMPRESSION_BOUND")
            crc_ok = True
    except TimeoutError:
        raise
    except (OSError, EOFError, ValueError, zlib.error) as err:
        error_type = "GZIP_DECODE_OR_BOUND"  # Never print binary/SQL/error text.
    unchanged = fingerprint(owned_file(p)) == fingerprint(before)
    return {
        "result":"VALIDATED" if (digest_ok and crc_ok and unchanged) else "FAILED",
        "sha256_ok":digest_ok,"gzip_crc_ok":crc_ok,
        "unmodified_during_read":unchanged,
        "size_bytes":before.st_size,
        "uncompressed_bytes":uncompressed,
        "failure_category":error_type,
        "content_disclosed":False,
    },uncompressed

def main():
    if pwd.getpwuid(os.geteuid()).pw_name != "githubops":
        raise RuntimeError("WRONG_VPS_IDENTITY")
    t0 = time.monotonic()
    s = ROOT.lstat()
    if not stat.S_ISDIR(s.st_mode) or s.st_uid != os.geteuid() or ROOT.is_symlink():
        raise RuntimeError("SEGMENTS_ROOT_UNSAFE")
    names = list(os.listdir(ROOT))
    if len(names) > MAX_FILES:
        raise RuntimeError("UNEXPECTED_SEGMENT_DIRECTORY_SIZE")
    metas = sorted(n for n in names if n.endswith(".meta"))
    if len(metas) != 25:
        raise RuntimeError("HISTORICAL_MANIFEST_COUNT_CHANGED")
    results = []
    total_uncompressed = 0
    stopped_by_budget = False
    for rank,n in enumerate(metas,1):
        m = META_PATTERN.fullmatch(n)
        if not m:
            raise RuntimeError("MANIFEST_NAME_UNEXPECTED")
        if int(m.group(2)) not in range(8):
            raise RuntimeError("INVALID_SEGMENT_PART")
        if m.group(3) is not None and int(m.group(3)) not in range(4):
            raise RuntimeError("INVALID_SEGMENT_SUBPART")
        meta_path = ROOT/n
        ms = owned_file(meta_path)
        if not 0 < ms.st_size <= MAX_META:
            raise RuntimeError("MANIFEST_LENGTH_OUT_OF_RANGE")
        content = meta_path.read_text(encoding="utf-8", errors="replace")
        sha, size = SHA_PATTERN.findall(content), SIZE_PATTERN.findall(content)
        if len(sha)!=1 or len(size)!=1:
            raise RuntimeError("MANIFEST_HASH_OR_SIZE_NOT_UNIQUE")
        expected_size = int(size[0])
        expected_sha = sha[0]
        gz = ROOT/(n[:-5] + ".sql.gz")
        try:
            summary, plain_bytes = check_payload(gz,expected_size,expected_sha,t0)
        except TimeoutError:
            stopped_by_budget=True
            break
        total_uncompressed += plain_bytes
        if total_uncompressed > MAX_TOTAL_UNCOMPRESSED:
            raise RuntimeError("TOTAL_UNCOMPRESSED_TOO_LARGE")
        summary["rank"] = rank
        summary["group"] = "A" if m.group(1)==BASES[0] else "B"
        results.append(summary)
    schema_path=ROOT/"schema.sql.gz"
    schema={"checked":False,"gzip_crc_ok":False,"sql_ddl_marker_present":False}
    if not stopped_by_budget:
        ss=owned_file(schema_path)
        if not 0<ss.st_size<=1024**2:
            raise RuntimeError("SCHEMA_ARCHIVE_UNEXPECTED_SIZE")
        before=fingerprint(ss)
        try:
            with gzip.open(schema_path,"rb") as f:
                blob=f.read(1024**2+1)
            schema={"checked":True,
                    "gzip_crc_ok":len(blob)<=1024**2,
                    "sql_ddl_marker_present":b"CREATE TABLE" in blob,
                    "unchanged":fingerprint(owned_file(schema_path))==before}
        except (OSError,EOFError,ValueError):
            schema={"checked":True,"gzip_crc_ok":False,
                    "sql_ddl_marker_present":False,"unchanged":False}
    successes=sum(x["result"]=="VALIDATED" for x in results)
    complete=(len(results)==25 and successes==25 and
              schema["gzip_crc_ok"] and schema["sql_ddl_marker_present"]
              and schema.get("unchanged",False))
    output={
        "schema":"moj.factory.vps.sql-segment-sha-gzip.readonly.v1",
        "segments_expected":25,
        "segments_checked":len(results),
        "segments_sha_crc_passed":successes,
        "segments_failed":len(results)-successes,
        "compressed_bytes_checked":sum(x["size_bytes"] for x in results),
        "uncompressed_bytes_crc_streamed":total_uncompressed,
        "group_counts":{
            "A_checked":sum(x["group"]=="A" for x in results),
            "B_checked":sum(x["group"]=="B" for x in results),
        },
        "failed_ranks_without_names":[x["rank"] for x in results if x["result"]!="VALIDATED"],
        "schema_gzip":schema,
        "full_historical_fragment_integrity_verified":complete,
        "verification_time_budget_exhausted":stopped_by_budget,
        "historical_database_consistency_verified":False,
        "current_live_database_backup_verified":False,
        "offsite_independent_copy_verified":False,
        "restore_test_verified":False,
        "sql_app_data_disclosed":False,
        "files_written":0,"files_deleted":0,"live_database_changes":0,
        "safe_to_cleanup_production":False,
        "elapsed_seconds":round(time.monotonic()-t0,2),
    }
    print("MOJ_FACTORY_VPS_SQL_SHA_CRC="+json.dumps(output,sort_keys=True),flush=True)

if __name__=="__main__":
    try:
        import zlib
        main()
    except Exception as exc:
        print("MOJ_FACTORY_VPS_SQL_SHA_CRC_FAILED="+type(exc).__name__+
              ":"+str(exc)[:64],file=sys.stderr,flush=True)
        sys.exit(1)
