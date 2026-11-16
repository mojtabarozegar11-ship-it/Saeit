#!/usr/bin/env python3
"""Read-only, conservative PR-to-main GitHub Actions merge-impact inventory.

NO network, GitHub API, cPanel/VPS, deployment, secrets, cron or deletion.
Never authorizes a merge. Unknown YAML syntax is treated as review-required.
This checks potential triggering, NOT whether workflow jobs write to a host.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
ON_LINE = re.compile(r"(?m)^on:[ \t]*(.*)$")
TOP_KEY = re.compile(r"(?m)^[A-Za-z_][\w-]*:[ \t]*")
EVENT = re.compile(r"(?m)^  ([A-Za-z_][\w-]*):[ \t]*(.*)$")
WRITER_TERMS = ("ssh ", "scp ", "rsync ", "crontab", "secrets.", "deploy",
                "publish", "installer", "cpanel", "restart.txt", "ftp ", "vps")


def items(raw: str) -> list[str]:
    raw = raw.strip()
    if raw.startswith("[") and raw.endswith("]"):
        raw = raw[1:-1]
    return [part.strip().strip("\"'") for part in raw.split(",") if part.strip()]


def sublist(block: str, key: str) -> list[str] | None:
    match = re.search(r"(?m)^    " + re.escape(key) + r":[ \t]*(.*)$", block)
    if not match:
        return None
    if match.group(1).strip():
        return items(match.group(1))
    values = []
    for line in block[match.end():].splitlines():
        if line.lstrip().startswith("#") or not line.strip():
            continue
        if not line.startswith("      - "):
            break
        values.extend(items(line.strip()[2:]))
    return values


def includes_main(branches: list[str] | None) -> bool:
    if branches is None:
        return True
    if not branches:
        return True  # empty/invalid filter -> cannot prove non-trigger
    # Negations and nonstandard patterns are never used to prove safety.
    return any(p.startswith("!") or fnmatch.fnmatchcase("main", p) for p in branches)


def matches_changed_path(patterns: list[str] | None, changed: list[str]) -> bool:
    if patterns is None or not patterns:
        return bool(changed)
    for p in patterns:
        # GitHub '!' exclusions and unsupported extglobs need human review.
        if p.startswith("!") or any(ch in p for ch in "@+?()"):
            return True
        for path in changed:
            # fnmatch overmatches '*' across '/', which is safe for NO-GO.
            if fnmatch.fnmatchcase(path, p):
                return True
    return False


def inspect_text(name: str, source: str, changed: list[str]) -> dict:
    found = ON_LINE.search(source)
    if not found:
        return {"workflow": name, "classification": "unknown_on_syntax",
                "matching_paths": [], "writer_markers": []}
    remainder = source[found.end():]
    next_top = TOP_KEY.search(remainder)
    header = remainder[:next_top.start()] if next_top else remainder
    inline = found.group(1).split("#", 1)[0].strip()
    event_entries = list(EVENT.finditer(header))
    # A scalar/list top-level event is valid YAML and needs handling.
    inline_events = items(inline) if inline else []
    push = next((m for m in event_entries if m.group(1) == "push"), None)
    downstream = any(m.group(1) == "workflow_run" for m in event_entries)
    if "workflow_run" in inline_events:
        downstream = True
    possible_main_push = False
    patterns = None
    if push:
        rest = header[push.end():]
        next_event = EVENT.search(rest)
        block = rest[:next_event.start()] if next_event else rest
        possible_main_push = includes_main(sublist(block, "branches"))
        patterns = sublist(block, "paths")
    elif "push" in inline_events:
        possible_main_push = True
    # Different event formatting, YAML alias, or embedded flow map is UNKNOWN.
    if (inline and not inline_events) or (not inline and not event_entries):
        return {"workflow": name, "classification": "unknown_on_syntax",
                "matching_paths": [], "writer_markers": []}
    triggered = bool(downstream or (possible_main_push and matches_changed_path(patterns, changed)))
    markers = sorted(x for x in WRITER_TERMS if x in source.lower()) if triggered else []
    return {
        "workflow": name,
        "classification": ("possible_workflow_run" if downstream else
                           "possible_main_push" if triggered else "not_matched"),
        "matching_paths": changed if triggered and (patterns is None or downstream) else
                          [p for p in changed if any(
                              x.startswith("!") or fnmatch.fnmatchcase(p, x)
                              for x in (patterns or []))],
        "writer_markers": markers,
    }


def inspect(root: Path, changed: list[str]) -> dict:
    normalized = sorted(set(p.strip() for p in changed if p.strip()))
    if not normalized or any(p.startswith("/") or ".." in Path(p).parts for p in normalized):
        raise ValueError("CHANGED_PATHS_EMPTY_OR_UNSAFE")
    folder = root / ".github" / "workflows"
    files = sorted(folder.glob("*.yml")) + sorted(folder.glob("*.yaml"))
    results = []
    for path in files:
        if path.is_symlink() or not path.is_file():
            results.append({"workflow": path.name, "classification": "unknown_file",
                            "matching_paths": [], "writer_markers": []})
            continue
        try:
            data = path.read_bytes()
            if not 0 < len(data) <= 300_000:
                raise ValueError("UNUSUAL_WORKFLOW_SIZE")
            source = data.decode("utf-8", "strict")
            results.append(inspect_text(path.name, source, normalized))
        except (OSError, UnicodeError, ValueError):
            results.append({"workflow": path.name, "classification": "unknown_file",
                            "matching_paths": [], "writer_markers": []})
    blockers = [r for r in results if r["classification"] != "not_matched"]
    return {
        "schema": "mojtaba.bot.ai.source-main-merge-impact.v1",
        "scope": "offline_full_checkout_static_readonly",
        "changed_file_count": len(normalized),
        "workflow_files_scanned": len(files),
        "possible_trigger_count": sum(x["classification"].startswith("possible") for x in blockers),
        "unknown_count": sum(x["classification"].startswith("unknown") for x in blockers),
        "blockers": blockers,
        "merge_authorized": False,
        "live_deployment_authorized": False,
        "host_cleanup_authorized": False,
        "verdict": "NO_GO" if blockers or len(files) < 1000 else "REVIEW_REQUIRED",
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", type=Path, default=ROOT)
    ap.add_argument("--changed-paths-file", type=Path, required=True)
    ap.add_argument("--enforce", action="store_true",
                    help="Nonzero exit on possible workflow triggers or unknowns.")
    args = ap.parse_args()
    changed = args.changed_paths_file.read_text(encoding="utf-8").splitlines()
    report = inspect(args.repo_root, changed)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    if args.enforce and (report["verdict"] == "NO_GO" or
                         report["workflow_files_scanned"] < 1000):
        raise SystemExit(3)


if __name__ == "__main__":
    main()
