"""Fail-closed source audit: a TRON security-only merge must not deploy a site.

Scans the entire locally checked-out workflow directory, not a hand-curated
subset. This does not authorize production, wallet access, or GitHub release.
"""
from __future__ import annotations

import fnmatch
import re
from pathlib import Path

WORKFLOWS = Path(__file__).resolve().parents[1] / ".github" / "workflows"
SENSITIVE_SOURCE = (
    "services/mpw_trx_merchant_binding.py",
    "tests/test_mpw_trx_merchant_binding.py",
    "docs/MPW_TRON_MERCHANT_BOUNDARY_20261115.md",
    "tests/test_tron_merge_trigger_isolation_20261115.py",
)
WRITE_MARKERS = (
    r"\bssh\b", r"\bscp\b", r"\brsync\b", r"secrets\.",
    r"\bkubectl\b", r"\bdocker\s+(push|login)\b",
    r"\bpassenger\b", r"\brestart\.txt\b",
    r"\bcurl\b.{0,140}(?:-X\s*(?:POST|PUT|DELETE)|--data)",
    r"\bgh\s+(?:workflow|api|release)\b",
)


def _event_section(header: str, event: str) -> str | None:
    found = re.search(r"(?m)^  " + re.escape(event) + r":\s*(.*)$", header)
    if not found:
        return None
    rest = header[found.end():]
    nxt = re.search(r"(?m)^  [a-zA-Z_][\w-]*:\s*", rest)
    return found.group(1) + "\n" + (rest[:nxt.start()] if nxt else rest)


def _main_allowed(section: str) -> bool:
    match = re.search(r"(?m)^    branches:\s*(.*)$", section)
    if match is None:
        return True
    first = match.group(1).strip()
    if first.startswith("["):
        return bool(re.search(r"(?<![a-zA-Z])main(?![a-zA-Z])|[*]", first))
    if first and not first.startswith("#"):
        return first.strip("'\"") in ("main", "*", "**")
    tail = section[match.end():]
    options = []
    for line in tail.splitlines():
        if line.startswith("      - "):
            options.append(line.strip().removeprefix("- ").strip(" '\""))
        else:
            break
    return ("main" in options or "*" in options or "**" in options)


def _paths(section: str) -> list[str] | None:
    match = re.search(r"(?m)^    paths:\s*(.*)$", section)
    if match is None:
        return None  # No include filter: every source can trigger.
    inline = match.group(1).strip()
    if inline.startswith("[") and inline.endswith("]"):
        return [x.strip(" '\"") for x in inline[1:-1].split(",")]
    output = []
    for line in section[match.end():].splitlines():
        if line.startswith("      - "):
            output.append(line.strip()[2:].strip(" '\""))
        else:
            break
    return output


def _affects_tron(section: str) -> bool:
    paths = _paths(section)
    if paths is None:
        return True
    for raw_pattern in paths:
        pattern = raw_pattern.lstrip("!")
        for path in SENSITIVE_SOURCE:
            if raw_pattern.startswith("!"):
                # A negative pattern is not proof that a positive match is safe.
                continue
            if fnmatch.fnmatchcase(path, pattern) or (
                pattern.endswith("/**") and path.startswith(pattern[:-3] + "/")
            ):
                return True
    return False


def _unguarded_write_jobs(source: str) -> list[str]:
    job_root = re.search(r"(?m)^jobs:\s*$", source)
    if job_root is None:
        return ["unknown-jobs"] if any(re.search(x, source, re.I) for x in WRITE_MARKERS) else []
    tail = source[job_root.end():]
    starts = list(re.finditer(r"(?m)^  ([a-zA-Z_][a-zA-Z0-9_-]*):\s*$", tail))
    failed = []
    for idx, start in enumerate(starts):
        job_name = start.group(1)
        body = tail[start.end():starts[idx + 1].start() if idx + 1 < len(starts) else len(tail)]
        if not any(re.search(x, body, re.I) for x in WRITE_MARKERS):
            continue
        # Test-only, hard-disabled, and dispatch-only jobs never deploy on push.
        header = body.split("\n    steps:", 1)[0]
        hard_off = re.search(r"(?m)^    if:\s*(?:\$\{\{\s*false\s*\}\}|false)\s*$", header)
        dispatch_only = re.search(
            r"(?m)^    if:\s*(?:\$\{\{\s*)?github\.event_name\s*==\s*['\"]workflow_dispatch['\"]",
            header,
        )
        if not hard_off and not dispatch_only:
            failed.append(job_name)
    return failed


def find_unapproved_release_paths() -> list[tuple[str, str, list[str]]]:
    risky = []
    paths = sorted(WORKFLOWS.glob("*.yml")) + sorted(WORKFLOWS.glob("*.yaml"))
    if len(paths) < 1:
        raise AssertionError("Workflow inventory is unavailable")
    for path in paths:
        source = path.read_text(encoding="utf-8")
        job_pos = re.search(r"(?m)^jobs:\s*$", source)
        header = source[:job_pos.start()] if job_pos else source
        push = _event_section(header, "push")
        workflow_run = _event_section(header, "workflow_run")
        event_types = []
        if push is not None and _main_allowed(push) and _affects_tron(push):
            event_types.append("main-push")
        if workflow_run is not None:
            event_types.append("workflow-run")
        if event_types:
            unsafe = _unguarded_write_jobs(source)
            if unsafe:
                risky.append((path.name, ",".join(event_types), unsafe))
    return risky


def test_tron_security_merge_has_no_unguarded_workflow_side_effects():
    risks = find_unapproved_release_paths()
    assert risks == [], (
        "TRON checksum PR cannot merge while workflow side effects are possible: "
        + repr(risks[:35])
        + (" (truncated)" if len(risks) > 35 else "")
    )
