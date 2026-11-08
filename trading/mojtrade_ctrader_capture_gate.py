"""Fail-closed preflight for a *manual* cTrader CLI evidence capture.

This validates local files and the operator's capture manifest, NOT cTrader
authentication. It is read-only, never calls the broker, and cannot approve
trading. In particular, the CLI's 200-deal cap cannot prove completeness when
exactly 200 rows are returned for a UTC day.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re


ACCOUNT = re.compile(r"^[0-9]{1,20}$")
SHA256 = re.compile(r"^[a-f0-9]{64}$")
SOURCES = frozenset({"positions", "orders_history", "deals"})


class CaptureError(ValueError):
    """An unsafe or incomplete evidence capture."""


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise CaptureError("duplicate_manifest_key")
        result[key] = value
    return result


def _utc_stamp(raw: str) -> datetime:
    if not isinstance(raw, str) or not raw.endswith("Z"):
        raise CaptureError("non_utc_capture_timestamp")
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        raise CaptureError("invalid_capture_timestamp") from None
    if parsed.utcoffset() != timedelta(0):
        raise CaptureError("non_utc_capture_timestamp")
    return parsed


def _count(raw) -> int:
    if isinstance(raw, bool) or not isinstance(raw, int) or raw < 0:
        raise CaptureError("invalid_capture_count")
    return raw


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check_capture(manifest: dict, base_dir: Path) -> dict:
    """Check three SHA-bound local CLI outputs and their declared coverage."""
    if not isinstance(manifest, dict) or set(manifest) != {
        "account", "day", "source", "captures"
    }:
        raise CaptureError("invalid_manifest_shape")
    account, day = manifest["account"], manifest["day"]
    if not isinstance(account, str) or not ACCOUNT.fullmatch(account):
        raise CaptureError("invalid_account")
    try:
        target_day = date.fromisoformat(day)
    except (TypeError, ValueError):
        raise CaptureError("invalid_day") from None
    if target_day.isoformat() != day or manifest["source"] != "ctrader-cli":
        raise CaptureError("invalid_scope_or_source")
    captures = manifest["captures"]
    if not isinstance(captures, dict) or set(captures) != SOURCES:
        raise CaptureError("missing_cli_source")

    issues: list[str] = []
    root = base_dir.resolve()
    day_end = datetime.combine(target_day + timedelta(days=1),
                               datetime.min.time(), timezone.utc)
    for name in sorted(SOURCES):
        record = captures[name]
        required = {"file", "sha256", "captured_utc", "count"}
        required |= {"from_utc_day", "to_utc_day"} if name != "positions" else set()
        required |= {"available", "returned"} if name == "orders_history" else set()
        if not isinstance(record, dict) or set(record) != required:
            raise CaptureError(f"invalid_source_shape:{name}")
        if not isinstance(record["file"], str) or not record["file"]:
            raise CaptureError(f"invalid_file_path:{name}")
        local_file = (root / record["file"]).resolve()
        if root not in local_file.parents or not local_file.is_file():
            raise CaptureError(f"unsafe_or_missing_file:{name}")
        if local_file.stat().st_size == 0:
            raise CaptureError(f"empty_capture_file:{name}")
        digest = record["sha256"]
        if not isinstance(digest, str) or not SHA256.fullmatch(digest):
            raise CaptureError(f"invalid_sha256:{name}")
        actual = _sha256_file(local_file)
        if digest != actual:
            issues.append(f"hash_mismatch:{name}")
        captured = _utc_stamp(record["captured_utc"])
        count = _count(record["count"])
        if captured < day_end:
            issues.append(f"capture_before_utc_day_end:{name}")
        if name in ("orders_history", "deals"):
            if record["from_utc_day"] != day or record["to_utc_day"] != day:
                issues.append(f"incomplete_utc_day_scope:{name}")
        if name == "orders_history":
            returned, available = _count(record["returned"]), _count(record["available"])
            if count != returned or available != returned or returned > 500:
                issues.append("orders_history_incomplete_or_inconsistent")
        elif name == "deals" and count >= 200:
            # At exactly 200, the CLI's hard limit makes completeness unknown.
            issues.append("deals_at_ambiguous_cli_limit")
    return {
        "account": account, "day": day,
        "coverage_plausible": not issues,
        "issues": sorted(issues),
        "broker_source_authenticated": False,
        "commercial_readiness": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Offline cTrader CLI capture preflight")
    parser.add_argument("--manifest", required=True, type=Path)
    args = parser.parse_args()
    try:
        with args.manifest.open("r", encoding="utf-8") as source:
            manifest = json.load(source, object_pairs_hook=_unique_object)
        result = check_capture(manifest, args.manifest.parent)
    except (OSError, ValueError) as exc:
        # Never print the capture files, account credentials, or raw manifest.
        print(json.dumps({"coverage_plausible": False,
                          "broker_source_authenticated": False,
                          "commercial_readiness": False,
                          "error": type(exc).__name__}, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0 if result["coverage_plausible"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
