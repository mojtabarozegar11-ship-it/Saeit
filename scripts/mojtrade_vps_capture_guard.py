#!/usr/bin/env python3
"""Local, fail-closed guard for a *prospective* fixed-venue public market feed.

No GitHub dependency, brokerage access, order submission, signal publication,
service installation or schedule modification. ``--check`` is read-only.
``--run`` is an explicitly invoked one-shot private evidence observation.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import stat
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import mojtrade_forward_bar_capture as capture
import mojtrade_market_quote_evidence as quotes
import mojtrade_observe_market as observer


SCHEMA = "mojtrade.vps-capture-guard.v1"
MIN_FREE_BYTES = 2 * 1024 ** 3 + 16 * 1024 ** 2
MIN_FREE_INODES = 16
FIRST_CAPTURE_MINUTE = 5
LAST_CAPTURE_MINUTE = 25
O_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
REQUIRED_SOURCES = (
    "mojtrade_observe_market.py",
    "mojtrade_market_quote_evidence.py",
    "mojtrade_forward_bar_capture.py",
    "mojtrade_vps_capture_guard.py",
)
PUBLIC_VENUES = {
    observer.SOURCE: observer._fetch_candles,
    observer.KRAKEN_SOURCE: observer._fetch_kraken_candles,
}


class GuardReject(ValueError):
    """Private runtime, disk, timing, source or evidence gate failed."""


def _no_symlink_ancestors(path):
    if not path.is_absolute() or any(part == ".." for part in path.parts):
        raise GuardReject("absolute_path_without_traversal_required")
    for item in (path, *path.parents):
        if item.is_symlink():
            raise GuardReject("symlink_path_component_forbidden")


def _owner_private_dir(parent):
    _no_symlink_ancestors(parent)
    if not parent.is_dir():
        raise GuardReject("private_directory_missing")
    meta = parent.stat()
    if (meta.st_uid != os.geteuid() or stat.S_IMODE(meta.st_mode) != 0o700):
        raise GuardReject("private_directory_must_be_owner_0700")


def _file_fingerprints(source_dir):
    folder = Path(source_dir)
    _no_symlink_ancestors(folder)
    if not folder.is_dir():
        raise GuardReject("source_directory_missing")
    if folder.stat().st_uid != os.geteuid() or folder.stat().st_mode & 0o022:
        raise GuardReject("source_directory_untrusted_permissions")
    hashes = {}
    for name in REQUIRED_SOURCES:
        path = folder / name
        _no_symlink_ancestors(path)
        try:
            meta = path.stat()
        except OSError as exc:
            raise GuardReject("required_source_missing:" + name) from exc
        if (not stat.S_ISREG(meta.st_mode) or meta.st_uid != os.geteuid()
                or meta.st_mode & 0o022 or not 0 < meta.st_size <= 300_000
                or meta.st_nlink != 1):
            raise GuardReject("required_source_unsafe:" + name)
        # Fingerprints establish observed local bytes, not remote authenticity.
        hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def _last_evidence(journal, venue, symbol):
    _no_symlink_ancestors(journal)
    if not journal.exists():
        return {"journal_exists": False, "observations": 0, "last_close_utc": None}
    try:
        fd = os.open(journal, os.O_RDONLY | os.O_NONBLOCK | O_NOFOLLOW)
    except OSError as exc:
        raise GuardReject("journal_cannot_be_read_safely") from exc
    try:
        meta = os.fstat(fd)
        if (not stat.S_ISREG(meta.st_mode) or meta.st_uid != os.geteuid()
                or meta.st_nlink != 1 or stat.S_IMODE(meta.st_mode) != 0o600
                or meta.st_size > capture.MAX_BYTES):
            raise GuardReject("journal_permissions_or_size_invalid")
        try:
            fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise GuardReject("journal_writer_busy") from exc
        with os.fdopen(fd, "rb") as source:
            fd = -1
            raw = source.read(capture.MAX_BYTES + 1)
        try:
            entries = capture._read_rows(raw)
        except (capture.CaptureReject, KeyError, TypeError, ValueError) as exc:
            raise GuardReject("journal_evidence_integrity_invalid") from exc
    finally:
        if fd >= 0:
            os.close(fd)
    if any(entry["observation"]["venue_claim"] != venue or
           entry["observation"]["symbol"] != symbol for entry in entries):
        raise GuardReject("journal_mixed_venue_or_symbol_forbidden")
    if any("quote_receipt" not in entry["observation"] for entry in entries):
        raise GuardReject("journal_missing_same_venue_quote_evidence")
    return {
        "journal_exists": True,
        "observations": len(entries),
        "last_close_utc": entries[-1]["observation"]["bar_close_utc"] if entries else None,
    }


def _existing_lock_is_private(journal):
    """Inspect an old lock without creating or acquiring it during --check.

    Active-writer exclusion remains the responsibility of _singleton in --run.
    """
    lock_path = Path(str(journal) + ".lock")
    _no_symlink_ancestors(lock_path)
    try:
        fd = os.open(lock_path, os.O_RDONLY | os.O_NONBLOCK | O_NOFOLLOW)
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise GuardReject("existing_lock_cannot_be_inspected") from exc
    try:
        meta = os.fstat(fd)
        if (not stat.S_ISREG(meta.st_mode) or meta.st_uid != os.geteuid()
                or meta.st_nlink != 1 or stat.S_IMODE(meta.st_mode) != 0o600):
            raise GuardReject("existing_lock_permissions_invalid")
    finally:
        os.close(fd)
    return True


def preflight(journal, symbol, venue, *, source_dir=None, now=None,
              free_bytes=None, free_inodes=None, require_capture_window=False):
    """Check disk/runtime/evidence with zero writes or market-data requests.

    Clock and free-space overrides are only injectable for offline test fixtures;
    CLI always measures the real clock, filesystem bytes and free inodes.
    """
    if symbol not in observer.PRODUCTS or venue not in PUBLIC_VENUES:
        raise GuardReject("only_supported_public_symbol_and_quoted_venue")
    clock = datetime.now(timezone.utc) if now is None else now
    if not isinstance(clock, datetime) or clock.tzinfo is None:
        raise GuardReject("timezone_aware_clock_required")
    clock = clock.astimezone(timezone.utc)
    if require_capture_window and not FIRST_CAPTURE_MINUTE <= clock.minute < LAST_CAPTURE_MINUTE:
        raise GuardReject("outside_safe_hourly_observation_window")

    target = Path(journal)
    _no_symlink_ancestors(target)
    _owner_private_dir(target.parent)
    filesystem = os.statvfs(target.parent) if free_bytes is None or free_inodes is None else None
    available = (filesystem.f_bavail * filesystem.f_frsize
                 if free_bytes is None else free_bytes)
    available_inodes = filesystem.f_favail if free_inodes is None else free_inodes
    if type(available) is not int or available < MIN_FREE_BYTES:
        raise GuardReject("insufficient_disk_reserve_2gib_plus_16mib")
    if type(available_inodes) is not int or available_inodes < MIN_FREE_INODES:
        raise GuardReject("insufficient_free_inodes")
    lock_exists = _existing_lock_is_private(target)
    package = Path(__file__).resolve().parent if source_dir is None else Path(source_dir)
    fingerprints = _file_fingerprints(package)
    evidence = _last_evidence(target, venue, symbol.replace("-", "/"))
    return {
        "schema": SCHEMA,
        "status": "LOCAL_READINESS_ONLY_NOT_ACTIVATED",
        "symbol": symbol,
        "venue_claim": venue,
        "free_bytes": available,
        "required_free_bytes": MIN_FREE_BYTES,
        "free_inodes": available_inodes,
        "required_free_inodes": MIN_FREE_INODES,
        "existing_private_lock": lock_exists,
        "capture_window_utc_minutes": [FIRST_CAPTURE_MINUTE, LAST_CAPTURE_MINUTE],
        "observed_source_sha256": fingerprints,
        **evidence,
        "remote_source_authenticity_verified": False,
        "vps_running_verified": False,
        "publication": "disabled",
        "execution": "disabled",
        "real_orders": 0,
    }


@contextmanager
def _singleton(journal):
    """One process per journal; lock is owner-only and remains on disk."""
    lock_path = Path(str(journal) + ".lock")
    _no_symlink_ancestors(lock_path)
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_RDWR | O_NOFOLLOW, 0o600)
    except OSError as exc:
        raise GuardReject("singleton_lock_open_failed") from exc
    try:
        meta = os.fstat(fd)
        if (not stat.S_ISREG(meta.st_mode) or meta.st_uid != os.geteuid()
                or meta.st_nlink != 1 or stat.S_IMODE(meta.st_mode) != 0o600):
            raise GuardReject("singleton_lock_unsafe")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise GuardReject("capture_already_running") from exc
        yield
    finally:
        os.close(fd)


def capture_once(journal, symbol, venue, *, source_dir=None, now=None,
                 free_bytes=None, source_fetcher=None, quote_fetcher=None):
    """Explicit one-shot, pinned-source public observation with no fallback.

    Only valid *same-venue quoted* observations may change the private journal.
    Synthetic injection parameters are used by offline tests, not the CLI.
    """
    # Never create even the private lock on an unsafe/full filesystem.
    baseline = preflight(journal, symbol, venue, source_dir=source_dir, now=now,
                         free_bytes=free_bytes, require_capture_window=True)
    with _singleton(journal):
        locked = preflight(journal, symbol, venue, source_dir=source_dir, now=now,
                           free_bytes=free_bytes, require_capture_window=True)
        if locked["observed_source_sha256"] != baseline["observed_source_sha256"]:
            raise GuardReject("runtime_source_changed_before_fetch")
        fetcher = PUBLIC_VENUES[venue] if source_fetcher is None else source_fetcher
        quote = quotes.fetch_public_quote if quote_fetcher is None else quote_fetcher
        try:
            event = capture.capture_public_once(
                symbol, venues=((venue, fetcher),), quote_fetcher=quote)
        except capture.CaptureReject as exc:
            raise GuardReject("public_market_capture_rejected") from exc
        if event["venue_claim"] != venue or "quote_receipt" not in event:
            raise GuardReject("same_venue_fresh_quote_required_no_write")
        # The upstream fetch may have consumed precious headroom or rotated files.
        after_fetch = preflight(journal, symbol, venue, source_dir=source_dir,
                                free_bytes=free_bytes)
        if after_fetch["observed_source_sha256"] != baseline["observed_source_sha256"]:
            raise GuardReject("runtime_source_changed_during_fetch")
        try:
            result = capture.append_private(event, journal)
        except capture.CaptureReject as exc:
            raise GuardReject("journal_write_validation_failed") from exc
    return {"schema": SCHEMA, "research_only": True, "real_orders": 0,
            "local_source_fingerprint_sha256": capture.sha(baseline["observed_source_sha256"]),
            "publication": "disabled", "execution": "disabled", **result}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Guarded public forward capture: defaults to read-only")
    parser.add_argument("--symbol", required=True, choices=observer.PRODUCTS)
    parser.add_argument("--venue", required=True, choices=sorted(PUBLIC_VENUES))
    parser.add_argument("--private-journal", required=True, type=Path)
    parser.add_argument("--run", action="store_true", help="explicit one-shot public capture")
    args = parser.parse_args(argv)
    try:
        result = (capture_once(args.private_journal, args.symbol, args.venue)
                  if args.run else preflight(args.private_journal, args.symbol, args.venue))
    except GuardReject as exc:
        print(json.dumps({"schema": SCHEMA, "status": "BLOCKED",
                          "reason": str(exc), "real_orders": 0}, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
