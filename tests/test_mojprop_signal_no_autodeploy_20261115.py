"""Fail-closed source audit: a signal inquiry fix must not deploy a site.

Scans the entire locally checked-out workflow directory, not a hand-curated
subset. This does not authorize production, wallet access, or GitHub release.
"""
from __future__ import annotations

import fnmatch
import re
from pathlib import Path
import sys

WORKFLOWS = Path(__file__).resolve().parents[1] / ".github" / "workflows"
SENSITIVE_SOURCE = (
    "templates/moj-prop-v4/index.html",
    "tests/test_mojprop_signal_plan_inquiry_20261115.py",
    "tests/test_mojprop_v4_receipt_contract_20261115.py",
    "tests/test_mojprop_signal_no_autodeploy_20261115.py",
)
WRITE_MARKERS = (
    r"\bssh\b", r"\bscp\b", r"\brsync\b", r"secrets\.",
    r"\bkubectl\b", r"\bdocker\s+(push|login)\b",
    r"\bpassenger\b", r"\brestart\.txt\b",
    r"\bcurl\b.{0,140}(?:-X\s*(?:POST|PUT|DELETE)|--data)",
    r"\bgh\s+(?:workflow|api|release)\b",
)


def _event_section(header: str, event: str) -> str | None:
    found = re.search(r"(?m)^  " + re.escape(event) + r":[ \t]*(.*)$", header)
    if not found:
        return None
    rest = header[found.end():]
    nxt = re.search(r"(?m)^  [a-zA-Z_][\w-]*:[ \t]*", rest)
    return found.group(1) + "\n" + (rest[:nxt.start()] if nxt else rest)


def _main_allowed(section: str) -> bool:
    match = re.search(r"(?m)^    branches:[ \t]*(.*)$", section)
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
    match = re.search(r"(?m)^    paths:[ \t]*(.*)$", section)
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


def _workflow_name(header: str, fallback: str) -> str:
    match = re.search(r"(?m)^name:[ \t]*(.+)$", header)
    return match.group(1).strip(" '\"") if match else fallback


def _run_upstreams(section: str) -> set[str]:
    """Only events from workflows that THIS source change actually triggers."""
    match = re.search(r"(?m)^    workflows:[ \t]*(.*)$", section)
    if match is None:
        return set()
    inline = match.group(1).strip()
    if inline.startswith("[") and inline.endswith("]"):
        return {x.strip(" '\"") for x in inline[1:-1].split(",") if x.strip()}
    if inline and not inline.startswith("#"):
        return {inline.strip(" '\"")}
    output = set()
    for line in section[match.end():].splitlines():
        if line.startswith("      - "):
            output.add(line.strip()[2:].strip(" '\""))
        else:
            break
    return output


def find_unapproved_release_paths() -> list[tuple[str, str, list[str]]]:
    """Transitively follow PR/main-push -> workflow_run jobs and deny side effects.

    An unrelated historical workflow_run must not be counted as a release
    caused by merging this PR. Conversely, workflow_run on CI triggered by
    our main push must be included even if it has no direct push paths.
    """
    paths = sorted(WORKFLOWS.glob("*.yml")) + sorted(WORKFLOWS.glob("*.yaml"))
    if len(paths) < 1:
        raise AssertionError("Workflow inventory is unavailable")
    inventory = []
    triggered = set()
    for path in paths:
        source = path.read_text(encoding="utf-8")
        job_pos = re.search(r"(?m)^jobs:\s*$", source)
        header = source[:job_pos.start()] if job_pos else source
        name = _workflow_name(header, path.stem)
        push = _event_section(header, "push")
        pr = _event_section(header, "pull_request")
        downstream = _event_section(header, "workflow_run")
        initial = (
            (push is not None and _main_allowed(push) and _affects_tron(push))
            or (pr is not None and _main_allowed(pr) and _affects_tron(pr))
        )
        event_type = "source-pr-or-main" if initial else ""
        entry = (path.name, name, source, downstream, event_type)
        inventory.append(entry)
        if initial:
            triggered.add(name)

    # A chain such as CI -> deploy preflight -> release can be longer than one
    # workflow_run edge. Follow all reachable names; never invoke any workflow.
    changed = True
    while changed:
        changed = False
        for filename, name, source, downstream, initial_event in inventory:
            if downstream is not None and name not in triggered:
                if _run_upstreams(downstream).intersection(triggered):
                    triggered.add(name)
                    changed = True

    risky = []
    for filename, name, source, downstream, initial_event in inventory:
        if name not in triggered:
            continue
        paths = _unguarded_write_jobs(source)
        if paths:
            cause = initial_event or "downstream-workflow-run"
            risky.append((filename, cause, paths))
    return risky


def test_unrelated_workflow_run_does_not_trigger_unwanted_release(tmp_path, monkeypatch):
    (tmp_path / "test.yml").write_text(
        'name: Tests\non:\n  pull_request:\njobs:\n  check:\n    runs-on: ubuntu-latest\n'
    )
    (tmp_path / "unrelated.yml").write_text(
        'name: Old backup restore\non:\n  workflow_run:\n'
        '    workflows: ["Unrelated 2020 backup"]\n    types: [completed]\n'
        'jobs:\n  deploy:\n    runs-on: ubuntu-latest\n'
        '    steps:\n      - run: ssh host destructive-operation\n'
    )
    monkeypatch.setattr(sys.modules[__name__], "WORKFLOWS", tmp_path)
    assert find_unapproved_release_paths() == []


def test_ci_followup_with_ssh_is_detected(tmp_path, monkeypatch):
    (tmp_path / "ci.yml").write_text(
        'name: CI\non:\n  push:\n    branches: [main]\njobs:\n'
        '  check:\n    runs-on: ubuntu-latest\n'
    )
    (tmp_path / "deploy.yml").write_text(
        'name: Auto ship\non:\n  workflow_run:\n'
        '    workflows: ["CI"]\n    types: [completed]\n'
        'jobs:\n  ship:\n    runs-on: ubuntu-latest\n'
        '    steps:\n      - run: ssh host deploy\n'
    )
    monkeypatch.setattr(sys.modules[__name__], "WORKFLOWS", tmp_path)
    assert find_unapproved_release_paths() == [
        ("deploy.yml", "downstream-workflow-run", ["ship"])
    ]


def test_path_limited_push_cannot_infer_other_files(tmp_path, monkeypatch):
    (tmp_path / "other.yml").write_text(
        'name: Other\non:\n  push:\n    paths: [scripts/unrelated.py]\n'
        'jobs:\n  deploy:\n    runs-on: ubuntu-latest\n'
        '    steps:\n      - run: ssh host deploy\n'
    )
    monkeypatch.setattr(sys.modules[__name__], "WORKFLOWS", tmp_path)
    assert find_unapproved_release_paths() == []


def test_unfiltered_push_with_ssh_cannot_escape_guard(tmp_path, monkeypatch):
    (tmp_path / "unsafe.yml").write_text(
        'name: Unsafe\non:\n  push:\n    branches: [main]\n'
        'jobs:\n  deploy:\n    runs-on: ubuntu-latest\n'
        '    steps:\n      - run: ssh host deploy\n'
    )
    monkeypatch.setattr(sys.modules[__name__], "WORKFLOWS", tmp_path)
    assert find_unapproved_release_paths() == [
        ("unsafe.yml", "source-pr-or-main", ["deploy"])
    ]


def test_dispatch_only_job_does_not_deploy_on_main_push(tmp_path, monkeypatch):
    (tmp_path / "manual.yml").write_text(
        'name: Manual\non:\n  push:\n    branches: [main]\n'
        '  workflow_dispatch:\njobs:\n  deploy:\n'
        "    if: github.event_name == 'workflow_dispatch'\n"
        '    runs-on: ubuntu-latest\n'
        '    steps:\n      - run: ssh host deploy\n'
    )
    monkeypatch.setattr(sys.modules[__name__], "WORKFLOWS", tmp_path)
    assert find_unapproved_release_paths() == []


def test_signal_inquiry_merge_has_no_unguarded_workflow_side_effects():
    risks = find_unapproved_release_paths()
    assert risks == [], (
        "Signal inquiry PR cannot merge while workflow side effects are possible: "
        + repr(risks[:35])
        + (" (truncated)" if len(risks) > 35 else "")
    )
