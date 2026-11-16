#!/usr/bin/env python3
"""Read-only, conservative PR-to-main GitHub Actions merge-impact inventory.

NO network, GitHub API, cPanel/VPS, deployment, secrets, cron or deletion.
Never authorizes a merge. Unknown YAML syntax is treated as review-required.
This checks potential triggering, NOT whether workflow jobs write to a host.
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
ON_LINE = re.compile(r"(?m)^on:[ \t]*(.*)$")
TOP_KEY = re.compile(r"(?m)^[A-Za-z_][\w-]*:[ \t]*")
EVENT = re.compile(r"(?m)^  ([A-Za-z_][\w-]*):[ \t]*(.*)$")
# Only byte-identical, separately reviewed no-host CI or manual-guard files
# may be suppressed; a changed blob makes the gate fail closed again.
REVIEWED_BLOBS = {
    "ci.yml": "255ab9a306cd5c94baf75ff23e97f89c368ac3d8",
    "django-ci.yml": "48a480daecd43e88ca8ccba4e4fd07a184fd9e72",
    "zomorod-app-pages-deploy.yml": "69d23980f04762a0ad0f771ef955894418da834d",
}

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



def git_blob_sha(source: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(source)).encode("ascii") + b"\0" + source).hexdigest()


def workflow_name(source: str, fallback: str) -> str:
    match = re.search(r"(?m)^name:\s*(.+?)\s*$", source)
    return match.group(1).strip("\"'") if match else fallback


def workflow_run_upstreams(source: str) -> tuple[list[str] | None, bool]:
    """Extract static upstream names and main-branch filter, never execute YAML."""
    start = ON_LINE.search(source)
    if not start:
        return None, True
    rem = source[start.end():]
    top = TOP_KEY.search(rem)
    header = rem[:top.start()] if top else rem
    events = list(EVENT.finditer(header))
    for i, entry in enumerate(events):
        if entry.group(1) != "workflow_run":
            continue
        body = header[entry.end():events[i + 1].start() if i + 1 < len(events) else len(header)]
        return sublist(body, "workflows"), includes_main(sublist(body, "branches"))
    return None, True


def verified_static_no_host_guard(filename: str, source: str) -> bool:
    if filename in ("ci.yml", "django-ci.yml"):
        return "ssh " not in source.lower() and "scp " not in source.lower() \
            and "secrets." not in source.lower()
    if filename == "zomorod-app-pages-deploy.yml":
        # Exactly the known publish job is explicitly manual; no other job.
        jobs = re.findall(r"(?m)^  ([A-Za-z_][\w-]*):\s*$",
                          source.split("\njobs:", 1)[-1])
        anchor = re.search(r"(?m)^  publish:\s*$", source)
        if jobs != ["publish"] or anchor is None:
            return False
        first = next((line.strip() for line in source[anchor.end():].splitlines()
                      if line.strip() and not line.lstrip().startswith("#")), "")
        return first == "if: github.event_name == 'workflow_dispatch'"
    return False


def inspect(root: Path, changed: list[str]) -> dict:
    normalized = sorted(set(p.strip() for p in changed if p.strip()))
    if not normalized or any(p.startswith("/") or ".." in Path(p).parts for p in normalized):
        raise ValueError("CHANGED_PATHS_EMPTY_OR_UNSAFE")
    folder = root / ".github" / "workflows"
    files = sorted(folder.glob("*.yml")) + sorted(folder.glob("*.yaml"))
    results = []
    known_sources = {}
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
            known_sources[path.name] = source
            results.append(inspect_text(path.name, source, normalized))
        except (OSError, UnicodeError, ValueError):
            results.append({"workflow": path.name, "classification": "unknown_file",
                            "matching_paths": [], "writer_markers": []})
    # workflow_run is only merge-causal when a new main run can complete a
    # matching upstream workflow, including transitive workflow_run chains.
    active_names = {
        workflow_name(known_sources[x["workflow"]], x["workflow"])
        for x in results if x["classification"] == "possible_main_push"
        and x["workflow"] in known_sources
    }
    pending = [x for x in results if x["classification"] == "possible_workflow_run"]
    while pending:
        progressed = False
        for row in pending[:]:
            upstream, permits_main = workflow_run_upstreams(
                known_sources.get(row["workflow"], "")
            )
            if not permits_main or (upstream is not None and not upstream):
                row["classification"] = "not_matched"
                pending.remove(row)
                progressed = True
            elif upstream and set(upstream).intersection(active_names):
                active_names.add(workflow_name(
                    known_sources[row["workflow"]], row["workflow"]))
                pending.remove(row)
                progressed = True
        if not progressed:
            break
    for row in pending:
        upstream, _ = workflow_run_upstreams(known_sources.get(row["workflow"], ""))
        # Missing filters are UNKNOWN and require review; unrelated upstreams
        # do not run merely because this PR is merged.
        row["classification"] = "unknown_workflow_run_upstream" if upstream is None \
            else "not_matched"

    reviewed = []
    for row in results:
        if row["classification"] != "possible_main_push":
            continue
        name = row["workflow"]
        source = known_sources.get(name)
        if (source is not None and name in REVIEWED_BLOBS and
                git_blob_sha(source.encode("utf-8")) == REVIEWED_BLOBS[name] and
                verified_static_no_host_guard(name, source)):
            row["classification"] = "verified_expected_ci_or_manual_guard"
            reviewed.append(name)
    blockers = [r for r in results if r["classification"] not in (
        "not_matched", "verified_expected_ci_or_manual_guard")]
    return {
        "schema": "mojtaba.bot.ai.source-main-merge-impact.v1",
        "scope": "offline_full_checkout_static_readonly",
        "changed_file_count": len(normalized),
        "workflow_files_scanned": len(files),
        "possible_trigger_count": sum(x["classification"].startswith("possible") for x in blockers),
        "unknown_count": sum(x["classification"].startswith("unknown") for x in blockers),
        "reviewed_safe_workflows": sorted(reviewed),
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
