#!/usr/bin/env python3
"""CPanel-local, privacy-minimized MojPlayWin operational evidence collector.

This is a deployment candidate, not an installed task. It executes only three
revision-pinned aggregate probes, stores validated fields, and never
contacts GitHub, an SSH relay, a payment network, or a mail sender.

All three probe sources must first be reviewed and installed in SOURCE_DIR.
"""

from __future__ import annotations

import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile

PRIVATE_ROOT = Path("/home/zomorod2/.private_mojplaywin_main_agents")
SOURCE_DIR = PRIVATE_ROOT / "mpw_readonly_sources"
REPORT = PRIVATE_ROOT / "mpw_readonly_health_latest.json"
LOCK = PRIVATE_ROOT / "mpw_readonly_health.lock"

PROBES = (
    ("cron", "mpw_payment_cron_heartbeat_readonly.py", "MPW_PAYMENT_CRON_HEARTBEAT", 65),
    ("paid", "mpw_paid_aggregate_readonly_c31.py", "MPW_PAID_AGGREGATE_READONLY", 100),
    ("flags", "mpw_runtime_flags_aggregate_readonly_c32.py", "MPW_RUNTIME_FLAGS_AGGREGATE_READONLY", 110),
)

# Git blob identities of the three audited sources. The cron source has been
# extended to report successful reconciliation; all copies must be repinned.
# A different revision must be reviewed and explicitly repinned before use.
PINNED_SOURCE_BLOBS = {
    "mpw_payment_cron_heartbeat_readonly.py": "4fdd9c7ccdcaad2443550708262bbeec35252334",
    "mpw_paid_aggregate_readonly_c31.py": "4baa575c841434aaff8dfefc67154220ed97f6ca",
    "mpw_runtime_flags_aggregate_readonly_c32.py": "cd79c83adaa7dfa1b54fd6dff31f0c4c9540e465",
}

SAFE_FIELDS = {
    "cron": ("cron_readable", "entry_once_per_minute", "heartbeat_fresh",
             "observed_run_count_last_five_minutes", "cron_heartbeat_distinguished_from_manual",
             "last_reconciler_success"),
    "paid": ("paid_intent_count", "rows_examined", "truncated",
             "walletless_persisted_credit_verified", "sku_scope_counts_examined",
             "sku_scope_verified_credits_examined", "customer_download_e2e_performed",
             "independent_mainnet_recheck_performed", "production_db_writes"),
    "flags": ("checkout_scope", "payment_flow_assessment",
              "live_paid_end_to_end_verified_by_this_probe", "private_data_emitted",
              "route_count_checked", "route_count_resolved", "http_view_invocations"),
}

REQUIRED = {
    "cron": SAFE_FIELDS["cron"],
    "paid": ("paid_intent_count", "rows_examined", "truncated",
             "walletless_persisted_credit_verified", "customer_download_e2e_performed",
             "independent_mainnet_recheck_performed", "production_db_writes"),
    "flags": ("checkout_scope", "payment_flow_assessment",
              "live_paid_end_to_end_verified_by_this_probe", "private_data_emitted",
              "route_count_checked", "route_count_resolved", "http_view_invocations"),
}
BOOLEAN_FIELDS = {
    "cron": ("cron_readable", "entry_once_per_minute", "heartbeat_fresh",
             "cron_heartbeat_distinguished_from_manual", "last_reconciler_success"),
    "paid": ("truncated", "customer_download_e2e_performed",
             "independent_mainnet_recheck_performed", "production_db_writes"),
    "flags": ("live_paid_end_to_end_verified_by_this_probe", "private_data_emitted"),
}
COUNT_FIELDS = {
    "cron": ("observed_run_count_last_five_minutes",),
    "paid": ("paid_intent_count", "rows_examined", "walletless_persisted_credit_verified"),
    "flags": ("route_count_checked", "route_count_resolved", "http_view_invocations"),
}
SKU_SCOPES = frozenset((
    "historical_trial_779", "mixed_with_trial_779", "configured_nontrial_public_sku",
    "outside_configured_public_sku", "public_allowlist_unavailable", "no_valid_products",
))


def private_directory_ok(path: Path) -> bool:
    """A 0600 file is not enough if its parent is accessible to others."""
    try:
        st = path.lstat()
    except OSError:
        return False
    return (stat.S_ISDIR(st.st_mode) and st.st_uid == os.getuid()
            and stat.S_IMODE(st.st_mode) == 0o700)


def summarize(name: str, obj: object) -> dict:
    """Accept only typed aggregate evidence; reject even whitelisted PII shapes."""
    if not isinstance(obj, dict):
        raise ValueError("unexpected_marker_shape")
    if any(key not in obj for key in REQUIRED[name]):
        raise ValueError("missing_required_aggregate_fields")
    safe = {key: obj[key] for key in SAFE_FIELDS[name] if key in obj}
    for key in BOOLEAN_FIELDS[name]:
        if key in safe and type(safe[key]) is not bool:
            raise ValueError("non_boolean_aggregate_field")
    for key in COUNT_FIELDS[name]:
        if key in safe and (type(safe[key]) is not int or safe[key] < 0):
            raise ValueError("invalid_aggregate_count")
    if name == "paid":
        if (safe["rows_examined"] > min(safe["paid_intent_count"], 100)
                or safe["walletless_persisted_credit_verified"] > safe["rows_examined"]
                or safe["truncated"] != (safe["paid_intent_count"] > safe["rows_examined"])):
            raise ValueError("inconsistent_paid_aggregate")
        if any(safe[field] for field in ("production_db_writes",
                                         "customer_download_e2e_performed",
                                         "independent_mainnet_recheck_performed")):
            raise ValueError("unexpected_mutating_or_e2e_probe")
    if name == "flags":
        if (safe["checkout_scope"] != "cryptocurrency_only"
                or safe["payment_flow_assessment"] != "NOT_TESTED_BY_READ_ONLY_PROBE"
                or safe["private_data_emitted"] or safe["live_paid_end_to_end_verified_by_this_probe"]
                or safe["route_count_checked"] != 6
                or safe["route_count_resolved"] != safe["route_count_checked"]
                or safe["http_view_invocations"] != 0):
            raise ValueError("unexpected_flags_or_scope")
    if name == "flags":
        runtime_flags = obj.get("crypto_runtime_feature_flags")
        if (not isinstance(runtime_flags, dict) or not runtime_flags
                or len(runtime_flags) > 32 or any(
                    not isinstance(k, str) or type(v) is not bool
                    for k, v in runtime_flags.items())):
            raise ValueError("unexpected_runtime_flags")
        safe["enabled_flag_count"] = sum(runtime_flags.values())
        safe["reported_flag_count"] = len(runtime_flags)
    if name == "paid":
        for key in ("sku_scope_counts_examined", "sku_scope_verified_credits_examined"):
            if key in safe:
                values = safe[key]
                if not isinstance(values, dict) or not all(
                    isinstance(k, str) and k in SKU_SCOPES
                    and type(v) is int and 0 <= v <= safe["rows_examined"]
                    for k, v in values.items()
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


def git_blob_id(payload: bytes) -> str:
    """Compare byte-for-byte against an audited GitHub source revision."""
    header = b"blob " + str(len(payload)).encode("ascii") + b"\0"
    return hashlib.sha1(header + payload).hexdigest()


def run_probe(name: str, filename: str, marker: str, seconds: int,
              *, source_dir: Path = SOURCE_DIR, python: str = sys.executable,
              pins: dict | None = None) -> dict:
    script = source_dir / filename
    if (not source_dir.is_dir() or source_dir.is_symlink() or
            not script.is_file() or script.is_symlink()):
        return {"status": "missing_verified_source"}
    pin = (PINNED_SOURCE_BLOBS if pins is None else pins).get(filename)
    if not isinstance(pin, str) or len(pin) != 40:
        return {"status": "source_pin_missing"}
    try:
        if script.stat().st_size > 256_000:
            return {"status": "source_too_large"}
        source = script.read_bytes()
    except OSError:
        return {"status": "source_unreadable"}
    if git_blob_id(source) != pin:
        return {"status": "source_revision_mismatch"}
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        # Feed the exact verified bytes, avoiding a second path read by Python.
        proc = subprocess.run([python, "-B", "-"], input=source,
                              stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                              timeout=seconds, env=env, check=False)
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
        summary = summarize(name, parse_marker(proc.stdout.decode("utf-8", "replace"), marker))
    except (ValueError, TypeError, json.JSONDecodeError):
        return {"status": "invalid_aggregate_marker"}
    return {"status": "completed", "summary": summary}


def build_report(*, source_dir: Path = SOURCE_DIR, python: str = sys.executable,
                 pins: dict | None = None) -> dict:
    results = {name: run_probe(name, script, marker, timeout,
                               source_dir=source_dir, python=python, pins=pins)
               for name, script, marker, timeout in PROBES}
    all_probes_completed = all(row["status"] == "completed" for row in results.values())
    cron_summary = results["cron"].get("summary", {})
    payment_scheduler_fresh = bool(
        cron_summary.get("cron_readable") is True
        and cron_summary.get("entry_once_per_minute") is True
        and cron_summary.get("heartbeat_fresh") is True
        and cron_summary.get("cron_heartbeat_distinguished_from_manual") is True
        and cron_summary.get("last_reconciler_success") is True
        and cron_summary.get("observed_run_count_last_five_minutes", 0) >= 2
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
    if not private_directory_ok(parent) or destination.is_symlink():
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
    if not private_directory_ok(PRIVATE_ROOT):
        return 3
    lock_fd = os.open(str(LOCK), os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        st = os.fstat(lock_fd)
        if st.st_uid != os.getuid() or stat.S_IMODE(st.st_mode) != 0o600:
            return 3
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

