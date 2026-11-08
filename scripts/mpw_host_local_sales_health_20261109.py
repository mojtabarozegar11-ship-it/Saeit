#!/usr/bin/env python3
"""CPanel-local, privacy-minimized MojPlayWin operational evidence collector.

This is a deployment candidate, not an installed task. It executes only the
four audited read-only probes, stores whitelisted aggregate fields, and never
contacts GitHub, an SSH relay, a payment network, or a mail sender.

The four probe sources must first be reviewed and installed in SOURCE_DIR.
"""

from __future__ import annotations

import datetime as dt
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

PRIVATE_ROOT = Path("/home/zomorod2/.private_mojplaywin_main_agents")
SOURCE_DIR = PRIVATE_ROOT / "mpw_readonly_sources"
REPORT = PRIVATE_ROOT / "mpw_readonly_health_latest.json"
LOCK = PRIVATE_ROOT / "mpw_readonly_health.lock"

PROBES = (
    ("cron", "mpw_payment_cron_heartbeat_readonly.py", "MPW_PAYMENT_CRON_HEARTBEAT", 65),
    ("paid", "mpw_paid_provenance_readonly_20261105.py", "MPW_PAID_PROVENANCE_READONLY", 100),
    ("flags", "mpw_payment_100_live_baseline_readonly_20261021.py", "MPW_PAYMENT_100_LIVE_BASELINE", 110),
    ("intake", "mpw_sales_intake_readonly_20261024.py", "MPW_INTAKE_READONLY", 180),
)

SAFE_FIELDS = {
    "cron": ("cron_readable", "entry_once_per_minute", "heartbeat_fresh",
             "observed_run_count_last_five_minutes", "cron_heartbeat_distinguished_from_manual"),
    "paid": ("paid_intent_count", "rows_examined", "truncated",
             "walletless_persisted_credit_verified", "sku_scope_counts_examined",
             "sku_scope_verified_credits_examined", "customer_download_e2e_performed",
             "independent_mainnet_recheck_performed", "production_db_writes"),
    "flags": ("checkout_scope", "payment_flow_assessment",
              "live_paid_end_to_end_verified_by_this_probe", "private_data_emitted"),
    "intake": ("result", "production_db_writes", "mail_content_read",
               "raw_identifiers_printed"),
}


def summarize(name: str, obj: object) -> dict:
    """Discard rows, emails, IDs, hashes, and unrecognized future fields."""
    if not isinstance(obj, dict):
        raise ValueError("unexpected_marker_shape")
    safe = {key: obj[key] for key in SAFE_FIELDS[name] if key in obj}
    if name == "flags":
        runtime_flags = obj.get("crypto_runtime_feature_flags")
        if isinstance(runtime_flags, dict):
            safe["enabled_flag_count"] = sum(value is True for value in runtime_flags.values())
            safe["reported_flag_count"] = len(runtime_flags)
    if name == "paid":
        for key in ("sku_scope_counts_examined", "sku_scope_verified_credits_examined"):
            if key in safe:
                values = safe[key]
                if not isinstance(values, dict) or not all(
                    isinstance(k, str) and k in (
                        "historical_trial_779", "mixed_with_trial_779",
                        "configured_nontrial_public_sku", "outside_configured_public_sku",
                        "public_allowlist_unavailable", "no_valid_products")
                    and type(v) is int and v >= 0 for k, v in values.items()
                ):
                    raise ValueError("unexpected_scope_counts")
    # Strict JSON serialization check guards accidental leakage through objects.
    json.dumps(safe, allow_nan=False)
    return safe


def parse_marker(stdout: str, marker: str) -> object:
    matches = [line[len(marker) + 1:] for line in stdout.splitlines()
               if line.startswith(marker + "=")]
    if len(matches) != 1:
        raise ValueError("missing_or_ambiguous_marker")
    return json.loads(matches[0])


def run_probe(name: str, filename: str, marker: str, seconds: int,
              *, source_dir: Path = SOURCE_DIR, python: str = sys.executable) -> dict:
    script = source_dir / filename
    if (not source_dir.is_dir() or source_dir.is_symlink() or
            not script.is_file() or script.is_symlink()):
        return {"status": "missing_verified_source"}
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        proc = subprocess.run([python, "-B", str(script)], capture_output=True,
                              text=True, timeout=seconds, env=env, check=False)
    except subprocess.TimeoutExpired:
        return {"status": "timeout"}
    except OSError:
        return {"status": "execution_unavailable"}
    if proc.returncode:
        # Do not record stderr, tracebacks or untrusted output.
        return {"status": "nonzero_exit"}
    if len(proc.stdout) > 1_000_000:
        return {"status": "output_too_large"}
    try:
        summary = summarize(name, parse_marker(proc.stdout, marker))
    except (ValueError, TypeError, json.JSONDecodeError):
        return {"status": "invalid_aggregate_marker"}
    return {"status": "completed", "summary": summary}


def build_report(*, source_dir: Path = SOURCE_DIR, python: str = sys.executable) -> dict:
    results = {name: run_probe(name, script, marker, timeout,
                               source_dir=source_dir, python=python)
               for name, script, marker, timeout in PROBES}
    all_probes_completed = all(row["status"] == "completed" for row in results.values())
    cron_summary = results["cron"].get("summary", {})
    payment_scheduler_fresh = bool(
        cron_summary.get("cron_readable") is True
        and cron_summary.get("entry_once_per_minute") is True
        and cron_summary.get("heartbeat_fresh") is True
    )
    return {
        "schema": 1,
        "checked_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "execution_location": "cpanel_local_no_relay",
        "monitor_completed": all_probes_completed,
        "payment_scheduler_fresh": payment_scheduler_fresh,
        "operational_evidence_fresh": all_probes_completed and payment_scheduler_fresh,
        "commercial_sale_or_customer_delivery_inferred": False,
        "results": results,
    }


def write_private_atomic(report: dict, *, destination: Path = REPORT) -> None:
    parent = destination.parent
    if not parent.is_dir() or parent.is_symlink() or destination.is_symlink():
        raise RuntimeError("invalid_private_report_directory")
    fd, pending = tempfile.mkstemp(prefix=".mpw-health-", suffix=".tmp", dir=parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(report, handle, sort_keys=True, ensure_ascii=False, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(pending, destination)
    finally:
        if os.path.exists(pending):
            os.unlink(pending)


def main() -> int:
    if not PRIVATE_ROOT.is_dir() or PRIVATE_ROOT.is_symlink():
        return 3
    lock_fd = os.open(str(LOCK), os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return 4
        report = build_report()
        write_private_atomic(report)
        # Cron output is intentionally an aggregate status only.
        print("MPW_HOST_LOCAL_READONLY=" + ("fresh" if report["operational_evidence_fresh"] else "incomplete"))
        return 0 if report["operational_evidence_fresh"] else 2
    finally:
        os.close(lock_fd)


if __name__ == "__main__":
    raise SystemExit(main())
