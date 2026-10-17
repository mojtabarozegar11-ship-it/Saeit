"""Fail-closed main-site-only design scope gate for the MojPlayWin presentation PR.

Uses the actual Git diff from the PR base, not a guessed protected-file inventory.
This is a SOURCE-level guard. It cannot attest to live payment or inventory health.
"""
from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys


ALLOWED_EXACT = frozenset({
    "core/mojplaywin_page_content.py",
    "core/mojplaywin_views.py",

    "core/templates/mojplaywin/section.html",
    "core/templates/mojplaywin/store.html",
    "core/templates/mojplaywin/theme.html",
    "core/templates/mojplaywin/footer.html",
    "core/templates/mojplaywin/founder_signature.html",
    "core/templates/mojplaywin/unified_visual_tokens.html",
    ".github/workflows/mojplaywin-commerce-scope-only.yml",
    "scripts/mojplaywin_commerce_scope.py",
    "tests/test_mojplaywin_commerce_scope.py",
})

ALLOWED_PREFIXES = (
    "core/tests/test_mojplaywin_",
    "core/static/site/mojplaywin-atelier/topic-images/venture-",
)

FORBIDDEN_TERMS = (
    "payment", "checkout", "wallet", "webhook", "settlement", "ledger",
    "order", "invoice", "refund", "product_model", "migration",
    "passenger", "wsgi", "deploy", "release", "farnaz",
)

SENSITIVE_PREFIXES = (
    "core/migrations/", "config/", "farnaz/", "saman/", "picm/",
    "mojtaba.roozegar/", "studio.Roham/", "zomorod/",
    "core/templates/core/", "core/templates/taniya_studio/",
    "core/templates/brands/",
)

def is_allowed_path(path: str) -> bool:
    if not path or path.startswith("/") or "\\" in path:
        return False
    p = pathlib.PurePosixPath(path)
    if ".." in p.parts or p.as_posix() != path:
        return False
    lower = path.lower()
    if any(lower.startswith(prefix.lower()) for prefix in SENSITIVE_PREFIXES):
        return False
    if path in ALLOWED_EXACT:
        return True
    if path.startswith("core/tests/test_mojplaywin_"):
        return path.endswith(".py") and not any(term in lower for term in FORBIDDEN_TERMS)
    prefix = "core/static/site/mojplaywin-atelier/topic-images/venture-"
    if path.startswith(prefix):
        return path.endswith(".svg") and not any(term in lower for term in FORBIDDEN_TERMS)
    return False

def check_entries(entries: list[tuple[str, str]]) -> list[str]:
    violations: list[str] = []
    if not entries:
        return ["No git changes detected: cannot verify the intended candidate."]
    for status, path in entries:
        # Reject removals and type/submodule changes even if the file is allowlisted.
        if status not in {"A", "M"}:
            violations.append(f"{status} {path}: modification type denied")
        if not is_allowed_path(path):
            violations.append(f"{status} {path}: outside presentation allowlist")
    return violations

def changed_files(base: str, head: str) -> list[tuple[str, str]]:
    # Both commits must be present; fail closed instead of skipping validation.
    for rev in (base, head):
        subprocess.run(["git", "rev-parse", "--verify", f"{rev}^{{commit}}"],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    data = subprocess.check_output(
        ["git", "diff", "--no-renames", "--name-status", "-z", f"{base}...{head}"]
    )
    chunks = data.decode("utf-8").split("\0")
    if chunks[-1] == "":
        chunks.pop()
    if len(chunks) % 2:
        raise ValueError("Malformed Git diff: status/path pair missing.")
    return list(zip(chunks[0::2], chunks[1::2]))

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", default="HEAD")
    args = parser.parse_args()
    try:
        entries = changed_files(args.base, args.head)
    except (OSError, ValueError, subprocess.CalledProcessError, UnicodeError) as exc:
        print(f"Scope gate blocked: unable to verify base/head: {exc}", file=sys.stderr)
        return 2
    failures = check_entries(entries)
    for status, name in entries:
        print(f"{status} {name}")
    if failures:
        for reason in failures:
            print(f"BLOCK: {reason}", file=sys.stderr)
        return 1
    print(f"PASS: {len(entries)} presentation-only changed files; no commerce or protected-site source changes.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
