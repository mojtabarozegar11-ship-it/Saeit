"""Owner-local, read-only schema history and cPanel quota observation.
No business rows, credentials, application writes, dumps, or migrations.
"""
import json
import os
import pwd
import re
import stat
import subprocess
import sys
from pathlib import Path
from decimal import Decimal

ROOT = Path("/home/zomorod2/Saeit-staging")
OWNER = "zomorod2"
EXPECTED = (
    "0001_initial", "0002_provisional_profit_ledger", "0003_social_evidence",
    "0004_four_week_challenge", "0005_trade_origin_and_position_id",
    "0006_ten_plan_enrollment", "0007_equity_broker_source",
    "0008_prospect_contact_intake", "0009_plan1_invoice_gateway",
    "0010_reward_reserve_ledger", "0011_plan1_account_default",
    "0012_simulation_account", "0013_restore_legacy_account_default",
    "0014_simulation_invoice_owner", "0015_simulation_identity",
    "0016_simulation_event", "0017_simulation_event_head",
)
TABLES = tuple("prop_firm_" + x for x in (
    "propplan1invoice", "propplan1receipt", "tronsettlementledger",
    "proprewardreserveallocation", "proprewardcommitment",
    "propsimulationaccount", "propsimulationinvoiceowner", "propsimulationidentity",
    "propsimulationloginchallenge", "propsimulationevent",
))

def history(rows):
    names = set(rows)
    known = [name for name in EXPECTED if name in names]
    return {"known_recorded_migrations": known,
            "known_unrecorded_migrations": [name for name in EXPECTED if name not in names],
            "unknown_record_count": len(names - set(EXPECTED)),
            "contiguous_known_prefix": known == list(EXPECTED[:len(known)]),
            "migration_record_is_not_schema_proof": True}

def quota_summary(payload):
    out = {"recognized": False, "account_headroom_verified": False}
    if not isinstance(payload, dict):
        return out
    result = payload.get("result")
    if not isinstance(result, dict) or result.get("status") != 1:
        return out
    rows = result.get("data")
    if not isinstance(rows, list) or len(rows) > 8:
        return out
    matches = [row for row in rows if isinstance(row, dict) and row.get("id") == "diskusage"]
    if len(matches) != 1:
        return out
    row = matches[0]
    # Some cPanel versions return e.g. "6.73 GB", not a separate units field.
    # Never silently assume a unit or treat a rounded UI figure as exact quota.
    units = ("B", "bytes", "KB", "MB", "GB", "TB", "KiB", "MiB", "GiB", "TiB")
    def parse(value):
        if type(value) not in (str, int, float):
            return None
        match = re.fullmatch(r"([0-9]{1,12}(?:\.[0-9]{1,6})?)(?:\s+([A-Za-z]{1,5}))?", str(value).strip())
        if not match:
            return None
        number, unit = match.groups()
        unit = unit or row.get("units")
        if unit not in units:
            return None
        return number, unit
    used = parse(row.get("count"))
    if used is None:
        return out | {"reason": "usage_format_unrecognized"}
    if isinstance(row.get("max"), str) and row["max"].strip().lower() == "unlimited":
        return out | {"recognized": True, "reported_used": used[0],
                      "reported_units": used[1], "reported_limit": "unlimited",
                      "display_values_only": True}
    limit = parse(row.get("max"))
    if limit is None or Decimal(limit[0]) <= 0:
        return out | {"reason": "limit_format_unrecognized"}
    report = out | {"recognized": True, "reported_used": used[0],
                    "reported_units": used[1], "reported_limit": limit[0],
                    "reported_limit_units": limit[1], "display_values_only": True}
    if used[1] == limit[1]:
        report["reported_remaining"] = str(max(Decimal(0), Decimal(limit[0]) - Decimal(used[0])))
    return report


def quota():
    for binary in ("/usr/bin/uapi", "/usr/local/cpanel/bin/uapi"):
        try:
            info = os.stat(binary)
            if not stat.S_ISREG(info.st_mode) or info.st_uid not in (0, os.geteuid()) or info.st_mode & 0o022:
                continue
            for userarg in (["--user="+OWNER], []):
                p = subprocess.run([binary, "--output=json"] + userarg +
                    ["StatsBar", "get_stats", "display=diskusage"], capture_output=True,
                    timeout=12, env={"LC_ALL":"C","PATH":"/usr/bin:/bin","HOME":"/home/"+OWNER,"USER":OWNER})
                if p.returncode == 0 and 0 < len(p.stdout) <= 32768:
                    report = quota_summary(json.loads(p.stdout))
                    if report["recognized"]:
                        return report
        except (OSError, ValueError, subprocess.SubprocessError):
            continue
    return {"recognized": False, "account_headroom_verified": False, "reason": "no_recognized_uapi_response"}

def inspect():
    out = {"read_only": True, "business_rows_read": False, "migration_executed": False,
           "release_authorized": False, "database_metadata_complete": False}
    if os.geteuid() == 0 or pwd.getpwuid(os.geteuid()).pw_name != OWNER:
        return out
    out["quota"] = quota()
    try:
        if not ROOT.is_dir() or ROOT.resolve() != ROOT:
            return out
        os.chdir(ROOT)
        sys.path.insert(0, str(ROOT))
        os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
        import django
        django.setup()
        from django.db import connection
        if connection.vendor != "mysql":
            return out
        with connection.cursor() as c:
            c.execute("SELECT name FROM django_migrations WHERE app=%s", ["prop_firm"])
            rows = c.fetchmany(101)
            if len(rows) > 100:
                return out
            out["migration_history"] = history([r[0] for r in rows])
            marks = ",".join(["%s"]*len(TABLES))
            c.execute("SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_TYPE='BASE TABLE' AND TABLE_NAME IN ("+marks+")", list(TABLES))
            present = {r[0] for r in c.fetchall()}
            out["expected_table_presence"] = {t: t in present for t in TABLES}
            c.execute("SELECT COLUMN_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s AND COLUMN_NAME IN (%s,%s)",
                      ["prop_firm_propsimulationaccount","event_head_sequence","event_head_digest"])
            cols = {r[0] for r in c.fetchall()}
            out["event_head_columns_present"] = {col:col in cols for col in ("event_head_sequence","event_head_digest")}
        out["database_metadata_complete"] = True
    except Exception as exc:
        out["error_type"] = type(exc).__name__
    return out

if __name__ == "__main__":
    print("MOJPROP_MIGRATION_QUOTA_READONLY="+json.dumps(inspect(),sort_keys=True))
