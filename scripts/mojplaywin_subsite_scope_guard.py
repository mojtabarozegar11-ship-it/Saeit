#!/usr/bin/env python3
"""Fail-closed source scope check for redesign of ONLY the MojPlayWin main site.

Every independent subsite under mojplaywin.com, including undiscovered future
sites, is protected BY DEFAULT. The script intentionally has no subsite
blacklist as its sole protection: it permits only a narrow list of main-site
source assets and read-only tests.

Passing this guard does NOT prove production safety. The existing Passenger
deployment touches a shared Django application and invokes a restart; it
must NOT be used until independent topology, backups, real product/payment
integrity and an isolated release path are proven separately.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


# Only main-site resources are editable. EVERYTHING else is denied, including
# shared global config, Django/Passenger, DB, checkout, media, and unknown apps.
EXACT_ALLOWED = frozenset({
    "core/mojplaywin_atelier_preview_urls.py",
    "core/mojplaywin_editorial.py",
    "core/mojplaywin_views.py",
    "core/mojplaywin_web_views.py",
    "core/static/site/mojplaywin-atelier-v4.css",
    "quality/mojplaywin-acceptance-100.json",
    "quality/README-mojplaywin-100.md",
})
PREFIX_ALLOWED = (
    "core/static/site/mojplaywin-atelier/",
    "core/templates/mojplaywin/",
    "core/templates/brands/mojplaywin/",
)
TEST_PREFIXES = (
    "core/tests/test_mojplaywin_",
    "tests/test_mojplaywin_",
    "scripts/mojplaywin_",
    ".github/workflows/mojplaywin-",
)
# These names resemble allowed prefixes but can restart a shared application.
ABSOLUTE_DENY = frozenset({
    "scripts/deploy_mojplaywin_branding.py",
    ".github/workflows/mojplaywin-main-deploy.yml",
})
KNOWN_EXAMPLES = (
    "/mojtaba.roozegar/",
    "/picm/",
    "/studio.Roham/",
    "/saman/",
    "/zahra$$/",
    "/farnaz/",
    "/taniya/",
)


def permitted(path: str) -> bool:
    if path in ABSOLUTE_DENY or not path or path.startswith("/"):
        return False
    if "\\" in path or path.endswith("/") or Path(path).is_absolute():
        return False
    parts = Path(path).parts
    if "." in parts or ".." in parts or "//" in path:
        return False
    if path in EXACT_ALLOWED or any(path.startswith(prefix) for prefix in PREFIX_ALLOWED):
        return True
    if any(path.startswith(prefix) for prefix in TEST_PREFIXES):
        # Explicitly prevent production deployment tools even with matching name.
        if path in ABSOLUTE_DENY:
            return False
        if path.startswith(".github/workflows/"):
            return path.endswith((".yml", ".yaml"))
        return path.endswith(".py")
    return False


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], capture_output=True, text=True, check=True,
    ).stdout


def changed_paths(base: str, head: str) -> list[tuple[str, str]]:
    # Do NOT recognize renames: a rename out of a protected subsite is
    # represented as deletion + addition, and its source cannot be hidden.
    output = git("diff", "--name-status", "--no-renames", base, head, "--")
    changes: list[tuple[str, str]] = []
    for line in output.splitlines():
        action, sep, path = line.partition("\t")
        if not sep or not path:
            raise ValueError("Unexpected git diff record")
        changes.append((action, path))
    return changes


def evaluate(changes: list[tuple[str, str]]) -> dict:
    denied = [
        {"status": status, "path": path}
        for status, path in changes if not permitted(path)
    ]
    deletions = [
        {"status": status, "path": path}
        for status, path in changes if status.startswith("D")
    ]
    unexpected = [
        {"status": status, "path": path}
        for status, path in changes if status not in ("A", "M", "T", "D")
    ]
    # Even changed file MODE/TYPES are unsafe during a visual-only redesign.
    modes = [
        {"status": status, "path": path}
        for status, path in changes if status == "T"
    ]
    result = {
        "source_scope_accepted": not any((denied, deletions, unexpected, modes)),
        "all_independent_subsites_protected_by_default": True,
        "only_main_site_paths_may_change": True,
        "changed_file_count": len(changes),
        "denied_paths": denied,
        "deleted_paths": deletions,
        "type_changes": modes,
        "unexpected_status": unexpected,
        "release_authorized": False,
        "runtime_isolation_verified": False,
        "all_live_subsites_discovered": False,
        "live_subsites_preserved_verified": False,
        "warnings": [
            "Source path isolation is NOT proof of runtime isolation.",
            "Shared Passenger/Django can affect unknown subsite routes on restart.",
            "DO NOT merge or deploy until every live subsite is inventoried and tested, full restorable backup is verified, and a non-shared safe deployment path is proven.",
        ],
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--output", default="mojplaywin-subsite-source-isolation-report.json")
    opts = parser.parse_args()
    result = evaluate(changed_paths(opts.base, opts.head))
    result["base_sha"] = opts.base
    result["head_sha"] = opts.head
    Path(opts.output).write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(
        "MOJPLAYWIN_SUBSITE_SOURCE_SCOPE="
        + ("PASS" if result["source_scope_accepted"] else "FAIL")
    )
    print("MOJPLAYWIN_DEPLOY_ALLOWED=FALSE")
    print("Unknown independent subsites are protected by default.")
    for bad in result["denied_paths"] + result["deleted_paths"] + result["type_changes"]:
        print(f"BLOCKED {bad['status']} {bad['path']}")
    if not result["source_scope_accepted"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
