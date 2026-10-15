#!/usr/bin/env python3
"""Astra isolated daily public-source research cycle (no factory or commerce writes).

Daily append-only reports are stored in a distinct owner-private folder.
Cron may invoke repeatedly: one baseline and at most one immutable retry per 6-hour UTC slot.
No site, factory database, queue, publication, payment or migration access.
"""
import argparse
from datetime import datetime, timezone
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import sys

RADAR_PATH = Path(__file__).with_name("astra_independent_research_radar.py")


def _radar():
    if RADAR_PATH.is_symlink() or not RADAR_PATH.is_file():
        raise ValueError("radar source missing or symlinked")
    spec = importlib.util.spec_from_file_location("astra_private_radar", RADAR_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _private_directory(value):
    """Refuse symlinked paths and open filesystem permissions."""
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise ValueError("absolute private workspace required")
    if path.is_symlink():
        raise ValueError("symlink workspace forbidden")
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.is_symlink() or not path.is_dir():
        raise ValueError("invalid workspace")
    os.chmod(path, 0o700)
    return path


def _new_lock(path):
    fd = os.open(str(path), os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    if not stat.S_ISREG(os.fstat(fd).st_mode):
        os.close(fd)
        raise ValueError("invalid lock file")
    return os.fdopen(fd, "r+b")


def _inspect_existing(path, today):
    if path.is_symlink() or not path.is_file():
        raise ValueError("unsafe existing report")
    if path.stat().st_size > 2_000_000:
        raise ValueError("oversized existing report")
    data = json.loads(path.read_text(encoding="utf-8"))
    if (data.get("run_date_utc") != today or
            data.get("mode") != "private_public_signal_research_only" or
            data.get("factory_mutations") != 0 or
            data.get("publications") != 0 or
            data.get("payments") != 0):
        raise ValueError("existing report is not a recognized private record")
    return len(data.get("candidate_hypotheses", []))


def _historical_reference_digests(workspace, now):
    """Read bounded recent, isolated manifests; never infer verified buyer demand."""
    from datetime import timedelta
    cutoff = (now - timedelta(days=30)).strftime("%Y%m%d")
    seen = set()
    entries = []
    for p in workspace.iterdir():
        match = re.fullmatch(r"(?:daily|retry)-([0-9]{8})(?:-[0-3])?\.json", p.name)
        if match and cutoff <= match.group(1) <= now.strftime("%Y%m%d"):
            entries.append(p)
    if len(entries) > 160:
        raise ValueError("private research history exceeds safe read limit")
    for p in sorted(entries):
        if p.is_symlink() or not p.is_file() or p.stat().st_size > 2_000_000:
            raise ValueError("unsafe private research history")
        record = json.loads(p.read_text(encoding="utf-8"))
        if (record.get("mode") != "private_public_signal_research_only"
                or record.get("factory_mutations") != 0 or
                record.get("publications") != 0 or record.get("payments") != 0):
            raise ValueError("unrecognized research history")
        for item in record.get("candidate_hypotheses", []):
            for ref in item.get("preliminary_references", []):
                digest = ref.get("reference_sha256")
                if isinstance(digest, str) and re.fullmatch(r"[a-f0-9]{64}", digest):
                    seen.add(digest)
    return seen


def run_cycle(root, now=None, fetcher=None, fixture=None, source=None):
    """Build at most one legitimate report for UTC date. No destructive updates."""
    now = now if now is not None else datetime.now(timezone.utc)
    if not isinstance(now, datetime) or now.tzinfo is None:
        raise ValueError("timezone-aware clock required")
    now = now.astimezone(timezone.utc)
    radar = _radar()
    workspace = _private_directory(root)
    today = now.strftime("%Y%m%d")
    baseline = workspace / ("daily-" + today + ".json")
    slot = now.hour // 6
    with _new_lock(workspace / ".cycle.lock") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        if baseline.exists() or baseline.is_symlink():
            known = _inspect_existing(baseline, today)
            original = json.loads(baseline.read_text(encoding="utf-8"))
            if original.get("run_slot_utc") == slot:
                return {"status": "UNCHANGED", "date": today,
                        "topic_count": known}
            # An incomplete earlier report never blocks same-day research.
            # Preserve it byte for byte; retries are capped to four UTC slots.
            path = workspace / ("retry-" + today + "-" + str(slot) + ".json")
            if path.exists() or path.is_symlink():
                return {"status": "UNCHANGED", "date": today,
                        "topic_count": _inspect_existing(path, today)}
        else:
            path = baseline
        # Never overwrite either baseline or older retry reports.
        feeds, errors = {}, {}
        if fixture is not None:
            if source not in radar.FEEDS and source not in radar.HTML_SOURCES:
                raise ValueError("unrecognized fixture source")
            if not isinstance(fixture, bytes) or len(fixture) > radar.MAX_FEED_BYTES:
                raise ValueError("invalid fixture bytes")
            feeds[source] = fixture
        else:
            fetch = fetcher if fetcher is not None else radar.fetch_feed
            for name in sorted(set(radar.FEEDS).union(radar.HTML_SOURCES)):
                try:
                    feeds[name] = fetch(name)
                except (OSError, ValueError) as exc:
                    errors[name] = type(exc).__name__
        if not feeds:
            return {"status": "SOURCES_UNAVAILABLE", "date": today, "topic_count": 0}
        report = radar.research_report(feeds, now)
        report["feed_failures"].update(errors)
        previously_seen = _historical_reference_digests(workspace, now)
        all_refs = set()
        fresh_refs = set()
        for item in report["candidate_hypotheses"]:
            refs = {r["reference_sha256"] for r in item["preliminary_references"]}
            item["new_source_signal_count_30d"] = len(refs - previously_seen)
            all_refs.update(refs)
            fresh_refs.update(refs - previously_seen)
        report["novel_source_signals_30d"] = len(fresh_refs)
        report["repeated_source_signals_30d"] = len(all_refs & previously_seen)
        report["has_new_30d_source_signal"] = bool(fresh_refs)
        report["novelty_window_days"] = 30
        report["novel_source_is_verified_market_demand"] = False
        report["run_date_utc"] = today
        report["cycle_version"] = "astra_research_daily_v2"
        report["run_slot_utc"] = slot
        if (report["factory_mutations"] != 0 or report["publications"] != 0 or
                report["payments"] != 0 or report["commercial_products_built"] != 0 or
                any(item["status"] != "RESEARCH_REQUIRED" or
                    item["product_build_authorized"] or
                    item["store_publication_authorized"] or
                    item["payment_authorized"]
                    for item in report["candidate_hypotheses"])):
            raise ValueError("research-only invariants violated")
        radar.write_private_new(path, report)
        return {"status": "RECORDED", "date": today,
                "topic_count": len(report["candidate_hypotheses"]),
                "feed_count": len(feeds), "failure_count": len(report["feed_failures"]),
                "record_name": path.name, "new_source_signals": len(fresh_refs)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, help="Private absolute directory, separate from factory")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--fetch", action="store_true")
    mode.add_argument("--fixture", help="Offline XML or HTML fixture for tests")
    parser.add_argument("--source", default="nass_news", help="Fixed source identity for fixture")
    parser.add_argument("--now-utc", help="Offline fixture clock only")
    args = parser.parse_args(argv)
    if args.fetch and args.now_utc:
        parser.error("clock override forbidden for live data")
    now = (datetime.fromisoformat(args.now_utc.replace("Z", "+00:00"))
           if args.now_utc else None)
    raw = None
    if args.fixture:
        file = Path(args.fixture)
        if file.is_symlink() or not file.is_file() or file.stat().st_size > 512_000:
            raise ValueError("unsafe fixture")
        raw = file.read_bytes()
    result = run_cycle(args.root, now=now, fixture=raw, source=args.source)
    for key, value in sorted(result.items()):
        print("ASTRA_RESEARCH_" + key.upper() + "=" + str(value))
    if result["status"] == "SOURCES_UNAVAILABLE":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
