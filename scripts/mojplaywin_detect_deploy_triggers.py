#!/usr/bin/env python3
"""Read-only GitHub Actions trigger inventory for the MojPlayWin safety PR.

Does not authenticate to SSH, invoke a deployer, or mutate anything on a server.
Conservative heuristic review aid: not an authoritative CI/CD permission gate.
"""
from __future__ import annotations

import fnmatch
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
LEGACY_LOCKS = {
    # Legacy shared-content jobs must stay hard-stopped.
    "mojplaywin-active-home-editorials.yml": "deploy-active-home",
    "mojplaywin-legacy-content-deploy.yml": "deploy-content",
}
MANUAL_RELEASE_JOBS = {
    "mojplaywin-main-deploy.yml": "deploy-main",
    "mojplaywin-moj-prop-deploy.yml": "deploy",
    "mojplaywin-farnaz-deploy.yml": "deploy",
    "mojplaywin-saman-deploy.yml": "deploy-saman",
    "zomorod-app-pages-deploy.yml": "publish",
}
MAIN_MANUAL_JOB = ("mojplaywin-main-deploy.yml", "deploy-main")
CANDIDATE_MAIN_FILES = (
    "core/mojplaywin_views.py",
    "core/templates/mojplaywin/home.html",
    "core/templates/brands/mojplaywin/base.html",
    "core/templates/brands/mojplaywin/home.html",
    "core/templates/brands/mojplaywin/page.html",
    # Signal funnel merges must not silently publish sibling sites.
    "core/financial_brand_pages.py",
    "core/templates/core/financial_brand_page.html",
    "templates/moj-prop-v4/catalog/index.html",
    "templates/moj-prop/signals/index.html",
)
CANDIDATE_SAFETY_FILES = tuple(
    ".github/workflows/" + file for file in LEGACY_LOCKS
) + (
    *(f".github/workflows/{file}" for file in MANUAL_RELEASE_JOBS),
    ".github/workflows/mojplaywin-deploy-trigger-readonly-audit.yml",
    "tests/test_owner_manual_deploy_premerge_20261115.py",
    "scripts/mojplaywin_detect_deploy_triggers.py",
    "tests/test_mojplaywin_shared_deploy_hard_stop.py",
)
DEPLOY_MARKERS = (
    "secrets.", "ssh ", "scp ", "rsync ", "passenger", "restart.txt",
    "deploy", "cpanel", "zohal.pws-dns.net", "saeit-staging",
)


def event_block(header: str, event: str) -> str | None:
    match = re.search(r"(?m)^  " + re.escape(event) + r":[ \t]*(.*)$", header)
    if not match:
        return None
    if match.group(1).strip():
        return match.group(1).strip()
    remaining = header[match.end():]
    next_event = re.search(r"(?m)^  [a-zA-Z_][\w-]*:\s*", remaining)
    return remaining[:next_event.start() if next_event else len(remaining)]


def contains_main(text: str) -> bool:
    match = re.search(r"(?m)^    branches:[ \t]*(.*)$", text)
    if not match:
        return True  # no branch restriction means main is included
    tail = match.group(1)
    if tail:
        return bool(re.search(r"(?<![\w])(?:main|\*\*?)(?![\w])", tail))
    lines = text[match.end():].splitlines()
    for line in lines:
        if not line.startswith("      - "):
            break
        if re.search(r"\bmain\b|\*", line):
            return True
    return False


def paths_filter(text: str) -> list[str] | None:
    match = re.search(r"(?m)^    paths:[ \t]*(.*)$", text)
    if not match:
        return None
    inline = match.group(1).strip()
    if inline.startswith("["):
        return [part.strip(" \"'") for part in inline.strip("[]").split(",") if part.strip()]
    paths: list[str] = []
    for line in text[match.end():].splitlines():
        if not re.match(r"^      - ", line):
            break
        paths.append(line.strip()[2:].strip(" \"'"))
    return paths


def can_match(pattern: str, path: str) -> bool:
    if not pattern or pattern.startswith("!"):
        return True  # fail conservative on exclusions/unknown patterns
    return fnmatch.fnmatchcase(path, pattern) or (
        pattern.endswith("/**") and path.startswith(pattern[:-3] + "/")
    )


def manual_release_job_guarded(source: str, header: str, job: str,
                               *, require_static_owner_approval: bool = False) -> bool:
    """Only an explicit manual dispatch may execute a release job.

    GitHub Actions permits a folded YAML condition, so normalize both one-line
    and folded forms before comparing the safety predicate.
    """
    if event_block(header, "workflow_dispatch") is None:
        return False
    anchor = re.search(r"(?m)^  " + re.escape(job) + r":\s*$", source)
    if anchor is None:
        return False
    tail = source[anchor.end():]
    tail = re.split(r"(?m)^  [a-zA-Z][\w-]+:\s*$", tail, maxsplit=1)[0]
    head = tail.split("\n    steps:", 1)[0]
    condition_match = re.search(
        r"(?ms)^    if:\s*(.*?)(?=\n    (?:runs-on|timeout-minutes|needs|strategy|environment):|\Z)",
        head,
    )
    if condition_match is None:
        return False
    condition = " ".join(line.strip() for line in condition_match.group(1).splitlines())
    condition = condition.replace(">-", " ").replace(">", " ").strip()
    condition = " ".join(condition.split())
    allowed = "github.event_name == 'workflow_dispatch'"
    if require_static_owner_approval:
        if "owner_approved_static_release:" not in header:
            return False
        allowed += " && inputs.owner_approved_static_release == true"
    return condition == allowed or condition.startswith(allowed + " && ")
def manual_main_deployment_guarded(source: str, header: str) -> bool:
    return manual_release_job_guarded(source, header, MAIN_MANUAL_JOB[1])


def inspect(filename: Path) -> dict:
    source = filename.read_text(encoding="utf-8")
    match = re.search(r"(?m)^jobs:\s*$", source)
    header = source[:match.start()] if match else source
    push = event_block(header, "push")
    downstream = event_block(header, "workflow_run")
    relevant = push is not None and contains_main(push)
    patterns = paths_filter(push) if relevant else []
    candidate_files = CANDIDATE_MAIN_FILES + CANDIDATE_SAFETY_FILES
    affected = [
        p for p in candidate_files
        if relevant and (patterns is None or any(can_match(pattern, p) for pattern in patterns))
    ]
    name = filename.name
    job = LEGACY_LOCKS.get(name)
    manual_guarded = (manual_release_job_guarded(
        source, header, MANUAL_RELEASE_JOBS[name],
        require_static_owner_approval=name == "mojplaywin-moj-prop-deploy.yml")
        if name in MANUAL_RELEASE_JOBS else None)
    main_guarded = manual_guarded if name == MAIN_MANUAL_JOB[0] else None
    locked = bool(
        job and re.search(
            r"(?m)^  " + re.escape(job) + r":\s*\n"
            r"(?:(?!^  [\w-]+:)[\s\S])*?^    if: \$\{\{ false \}\}\s*$",
            source
        )
    )
    return {
        "workflow": name,
        "runs_after_workflow": downstream is not None,
        "main_push": relevant,
        "main_push_unfiltered": relevant and patterns is None,
        "triggered_by_candidate_paths": affected,
        "deployer_indicators": [x for x in DEPLOY_MARKERS if x.lower() in source.lower()],
        "guarded_job": job,
        "guarded_job_locked": locked if job else None,
        "manual_main_deployment_guarded": main_guarded,
        "manual_release_job_guarded": manual_guarded,
    }


def main() -> None:
    all_files = sorted(WORKFLOWS.glob("*.yml")) + sorted(WORKFLOWS.glob("*.yaml"))
    inspected = [inspect(file) for file in all_files]
    unlocked_legacy = [
        v["workflow"] for v in inspected if v["guarded_job"] and not v["guarded_job_locked"]
    ]
    main_site_manual_only = any(
        v["workflow"] == MAIN_MANUAL_JOB[0] and v["manual_main_deployment_guarded"]
        for v in inspected
    )
    blocked_manual_releases = sorted(
        file for file in MANUAL_RELEASE_JOBS
        if not any(v["workflow"] == file and v["manual_release_job_guarded"]
                   for v in inspected)
    )
    review = [
        v for v in inspected
        if v["runs_after_workflow"] or (v["triggered_by_candidate_paths"] and not v["guarded_job_locked"])
    ]
    report = {
        "scope": "SOURCE ONLY; NEVER AUTHORIZES DEPLOYMENT",
        "workflows_scanned": len(inspected),
        "legacy_jobs_hard_stopped": not unlocked_legacy,
        "main_site_deploy_manual_only": main_site_manual_only,
        # Keep old field for existing dashboards; include the newly audited
        # SAMAN publisher and expose a correctly labelled aggregate.
        "four_release_jobs_manual_only": not blocked_manual_releases,
        "release_jobs_manual_only_count": len(MANUAL_RELEASE_JOBS),
        "five_release_jobs_manual_only": not blocked_manual_releases,
        "unguarded_release_jobs": blocked_manual_releases,
        "unlocked_legacy": unlocked_legacy,
        "other_trigger_paths_require_manual_review": review,
        "unrestricted_push_to_main": [
            {"name": v["workflow"], "deployer_indicators": v["deployer_indicators"]}
            for v in inspected if v["main_push_unfiltered"]
        ],
        "production_isolation_verified": False,
        "release_authorized": False,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if unlocked_legacy or blocked_manual_releases or not main_site_manual_only:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
