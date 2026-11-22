#!/usr/bin/env python3
"""Two read-only proofs: reviewed migration branch provenance and live backup scope.

--check-source: verify exact archived legacy (10) and new isolated (6) source
blobs plus declared in-app dependencies, with zero DB access.
--check-host: tenant-only SELECT read of isolated MariaDB schema/migration names
and streaming inspection of two existing host-only backup files.

NEITHER path executes a migration, writes files, creates a backup or DB,
starts a worker, contacts a service, authorizes billing or claims a restore.
"""
from __future__ import annotations

import ast
import gzip
import hashlib
import json
import os
import pwd
import re
import stat
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
OWNER = "zomorod2"
APP = Path("/home/zomorod2/Saeit-mojplaywin-integrated-20261119")
PAYMENT_TABLE = "prop_firm_propsimulationpayment"
MAX_SQL_BYTES = 8 * 1024 * 1024

LEGACY = {
    "0001_initial": "7dab3828ea53ceaaaaabc7d3383a92eea8cb8cb5",
    "0002_provisional_profit_ledger": "b617d142e41c45a2c50fb1f0f8e06270b2b9121a",
    "0003_social_evidence": "bb75cdeac68612e874a8d0a4d9653329d065bf46",
    "0004_four_week_challenge": "3a5de790c9e4ce59bcb0315dac1a4efa5b65a4b1",
    "0005_trade_origin_and_position_id": "fd98d94b2494c8a91e95209bdf023083806db34c",
    "0006_ten_plan_enrollment": "b516cd5ef8958271da03c5143cb89ce5c6de948a",
    "0007_equity_broker_source": "da816812dc68171488b79206ad5ab0da1820bce7",
    "0008_prospect_contact_intake": "d85549ce0637752c8744f25dd5b2c31d145a3316",
    "0009_plan1_invoice_gateway": "743b7ee1877598554e0c9364eeebb900270e876b",
    "0010_reward_reserve_ledger": "8a0ab87b94643f665522c35dc0d62eaf1c9d1c06",
}
ISOLATED = {
    "0001_simulation_isolation": "c0a0984bcfd32d58773234f45bdb68c169519587",
    "0002_starter30_payment": "56ca5f89f4f447857fa02b8b7536224a6ba5ca85",
    "0003_payment_table_router_alignment": "b4cad624daad9e72d6fd23d99638524c6488e95a",
    "0004_simulation_payout_commitment": "31de86fd0cb754590777506a907ec2fabeb43c01",
    "0005_optional_payer_wallet": "d61bf104fb33141daf6b9a9b8959f48e3ac48a77",
    "0006_unique_invoice_receivers": "90c2af4c2ac813a3bed7279d695b72970c1e10f9",
}
BACKUPS = (
    (Path("/home/zomorod2/separated-backups/20261121/mojprop-isolated-db-consistent-20261121.sql.gz"),
     "9f9ba93a4f0139c59a6b14014b83f6170bc6c7b4963a928a2eec9cff1e0d2ebb"),
    (Path("/home/zomorod2/separated-backups/mojprop-db-security-20261121/mojprop-dedicated-20261121.sql.gz"),
     "321f30bc95903fa0be01c9b6a5f69a1ddcf06a82fb64837e04617c1dac091ad9"),
)


def git_blob(content: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(content)).encode("ascii") + b"\0" + content).hexdigest()


def parents_in_migration(content: bytes) -> set[str]:
    """Extract only literal prop_firm migration dependencies, without executing Python."""
    tree = ast.parse(content.decode("utf-8"))
    migrations = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Migration"]
    if len(migrations) != 1:
        raise ValueError("unexpected migration declaration")
    deps = [n.value for n in migrations[0].body
            if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name)
            and t.id == "dependencies" for t in n.targets)]
    if len(deps) != 1:
        raise ValueError("no unique dependency declaration")
    out = set()
    for node in ast.walk(deps[0]):
        if isinstance(node, ast.Tuple) and len(node.elts) == 2:
            a, b = node.elts
            if (isinstance(a, ast.Constant) and a.value == "prop_firm"
                    and isinstance(b, ast.Constant) and type(b.value) is str):
                out.add(b.value)
    return out


def check_sources(repo: Path) -> dict:
    records = []
    for label, chain, relative in (
        ("legacy_archive", LEGACY, "source-sync/20261120/prop_firm/migrations"),
        ("isolated_current", ISOLATED, "prop_firm/migrations"),
    ):
        previous = None
        for name, pinned in chain.items():
            path = repo / relative / (name + ".py")
            status = "MISSING"
            if path.is_file() and not path.is_symlink():
                try:
                    raw = path.read_bytes()
                    parent = parents_in_migration(raw)
                    status = ("MATCH" if git_blob(raw) == pinned
                              and parent == ({previous} if previous is not None else set())
                              else "DRIFT")
                except (OSError, UnicodeError, SyntaxError, ValueError):
                    status = "UNREADABLE"
            records.append({"branch": label, "name": name, "status": status})
            previous = name
    valid = len(records) == 16 and all(row["status"] == "MATCH" for row in records)
    return {
        "scope": "legacy_archive_10_and_isolated_6_blob_and_parent_proof",
        "checked": len(records),
        "matched": sum(x["status"] == "MATCH" for x in records),
        "all_source_proven": valid,
        "historical_migrations_copied_to_runtime": False,
        "live_migrations_applied": False,
        "restore_verified": False,
        "written_changes": 0,
        "components": records,
    }


def inspect_archive(path: Path, expected_sha: str, live_tables: set[str]) -> dict:
    """Read exact gzip bytes and return only counts/booleans, never SQL contents."""
    result = {
        "label": path.name,
        "digest_verified": False,
        "all_current_tables_in_archive": False,
        "exact_30_table_schema": False,
        "no_database_switch": False,
        "no_destructive_ddl": False,
        "rehearsed_independent_restore": False,
        "archived_migration_names_15_of_15": False,
        "archived_unique_receiver_marked_applied": False,
    }
    if (not path.is_absolute() or path.is_symlink() or not path.is_file()
            or path.stat().st_nlink != 1
            or stat.S_IMODE(path.stat().st_mode) & 0o077):
        return result
    try:
        blob = path.read_bytes()
        if len(blob) > 1024 * 1024 or hashlib.sha256(blob).hexdigest() != expected_sha:
            return result
        with gzip.open(path, "rb") as stream:
            sql = stream.read(MAX_SQL_BYTES + 1)
        if not sql or len(sql) > MAX_SQL_BYTES:
            return result
    except (OSError, EOFError, ValueError):
        return result
    names = re.findall(
        rb"(?im)^[ \t]*CREATE TABLE[ \t]+(?:IF NOT EXISTS[ \t]+)?\x60([^\x60]+)\x60", sql
    )
    table_names = {x.decode("utf-8", errors="replace") for x in names}
    # The mysqldump may place VALUES on following lines. Inspect the complete
    # semicolon-terminated migration INSERT; never expose row text or recipients.
    migration_marker = b"INSERT INTO " + bytes([96]) + b"django_migrations" + bytes([96])
    migration_values = (
        sql.split(migration_marker, 1)[1].split(b";", 1)[0]
        if migration_marker in sql else b""
    )
    result["archived_migration_names_15_of_15"] = (
        bool(migration_values)
        and all(name.encode() in migration_values for name in LEGACY)
        and all(name.encode() in migration_values for name in list(ISOLATED)[:5])
    )
    result["archived_unique_receiver_marked_applied"] = (
        b"0006_unique_invoice_receivers" in migration_values
    )
    result["digest_verified"] = True
    result["tables_defined"] = len(names)
    result["tables_matched"] = len(live_tables & table_names)
    result["all_current_tables_in_archive"] = len(live_tables) > 0 and live_tables <= table_names
    result["exact_30_table_schema"] = (
        len(names) == len(table_names) == len(live_tables) == 30 and table_names == live_tables
    )
    result["no_database_switch"] = not bool(re.search(
        rb"(?im)^[ \t]*(?:CREATE|ALTER|DROP)[ \t]+(?:DATABASE|SCHEMA)\b|^[ \t]*USE[ \t]+", sql
    ))
    result["no_destructive_ddl"] = not bool(re.search(
        rb"(?im)^[ \t]*(?:DROP|TRUNCATE)[ \t]+TABLE\b|^[ \t]*RENAME[ \t]+TABLE\b", sql
    ))
    # SQL checks alone are NEVER sufficient evidence of restore correctness.
    return result


def inspect_live() -> dict:
    if pwd.getpwuid(os.geteuid()).pw_name != OWNER or not APP.is_dir():
        raise PermissionError("live inspection only under authorized tenant")
    os.chdir(APP)
    sys.path.insert(0, str(APP))
    env_file = APP / ".env"
    if env_file.is_file():
        for line in env_file.read_text(encoding="utf8", errors="replace").splitlines():
            value = line.strip()
            if not value or value.startswith("#") or "=" not in value:
                continue
            key, raw = value.split("=", 1)
            key = key.strip()
            raw = raw.strip()
            if raw[:1] in ("'", '"') and raw[-1:] == raw[:1]:
                raw = raw[1:-1]
            if key:
                os.environ.setdefault(key, raw)
    os.environ["SAEIT_ENV"] = "production"
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django
    django.setup()
    from django.db import connections
    db = connections["mojprop"]
    with db.cursor() as cur:
        cur.execute("START TRANSACTION READ ONLY")
        try:
            tables = set(db.introspection.table_names(cur))
            cur.execute("SELECT name FROM django_migrations WHERE app = %s", ("prop_firm",))
            applied = {row[0] for row in cur.fetchall()}
            payment_count = None
            if PAYMENT_TABLE in tables:
                cur.execute("SELECT COUNT(*) FROM " + db.ops.quote_name(PAYMENT_TABLE))
                payment_count = cur.fetchone()[0]
            constraints = db.introspection.get_constraints(cur, PAYMENT_TABLE)
            unique_receiver = any(meta.get("unique") is True
                                  and meta.get("columns") == ["recipient"]
                                  for meta in constraints.values())
        finally:
            cur.execute("ROLLBACK")
    archive_rows = [inspect_archive(p, digest, tables) for p, digest in BACKUPS]
    return {
        "scope": "owner_mojprop_alias_read_only_snapshot_30_table_schema",
        "live_table_count": len(tables),
        "legacy_applied_count": len(applied & set(LEGACY)),
        "new_applied_count": len(applied & set(ISOLATED)),
        "historical_names_all_known": applied <= set(LEGACY) | set(ISOLATED),
        "recipient_unique_enforced_in_db": unique_receiver,
        "native_payment_rows": payment_count,
        "backups": archive_rows,
        "schema_archive_coverage_proven": all(x["exact_30_table_schema"]
                                               and x["digest_verified"] for x in archive_rows),
        "migration_archive_coverage_proven": all(
            x["archived_migration_names_15_of_15"]
            and not x["archived_unique_receiver_marked_applied"]
            for x in archive_rows
        ),
        "independent_restore_verified": False,
        "production_migration_approved": False,
        "financial_release_proven": False,
        "written_changes": 0,
        "status": "BLOCKED",
    }


def main(args: list[str]) -> int:
    if args == ["--check-source"]:
        report = check_sources(REPO_ROOT)
        print(json.dumps(report, sort_keys=True))
        return 0 if report["all_source_proven"] else 2
    if args == ["--check-host"]:
        print(json.dumps(inspect_live(), sort_keys=True))
        return 2  # Always fail closed until independent DB restore + DDL proof
    print("Only --check-source or --check-host (read-only) are supported.", file=sys.stderr)
    return 64


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
