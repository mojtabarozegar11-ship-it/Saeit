#!/usr/bin/env python3
"""Read-only comparison of Checkout source trees at two Git revisions."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

VERSION = "1.0.0"
SCHEMA = "checkout-version-compare.v1"
SENSITIVE_NAME = re.compile(
    r"(^|[._-])(secret|secrets|credential|credentials|token|private[._-]?key)([._-]|$)|"
    r"(^|/)\.env($|\.)|\.(pem|key|p12|pfx)$",
    re.IGNORECASE,
)


class CompareError(Exception):
    pass


def git(repo: Path, *args: str) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode:
        raise CompareError(result.stderr.decode("utf-8", "replace").strip() or "git command failed")
    return result.stdout


def safe_repo_path(value: str) -> str:
    p = PurePosixPath(value)
    if p.is_absolute() or not value or any(part in ("", ".", "..") for part in value.split("/")):
        raise CompareError("--path must be a non-empty repository-relative path without dot segments")
    return p.as_posix()


def resolve_commit(repo: Path, ref: str) -> str:
    if not ref or ref.startswith("-"):
        raise CompareError("revision must be a non-empty Git revision")
    return git(repo, "rev-parse", "--verify", f"{ref}^{{commit}}").decode().strip()


def entries_at(repo: Path, commit: str, subtree: str) -> dict[str, dict[str, object]]:
    raw = git(repo, "ls-tree", "-r", "-z", "--full-tree", commit, "--", subtree)
    files: dict[str, dict[str, object]] = {}
    for record in raw.split(b"\0"):
        if not record:
            continue
        metadata, path_bytes = record.split(b"\t", 1)
        mode, kind, blob = metadata.decode("ascii").split()
        path = path_bytes.decode("utf-8", "surrogateescape")
        if kind != "blob" or SENSITIVE_NAME.search(path):
            continue
        size = int(git(repo, "cat-file", "-s", blob).decode().strip())
        files[path] = {"mode": mode, "sha1": blob, "bytes": size}
    return files


def compare(repo: Path, base_ref: str, candidate_ref: str, subtree: str) -> dict[str, object]:
    repo = repo.resolve(strict=True)
    if not repo.is_dir():
        raise CompareError("--repo must name an existing directory")
    subtree = safe_repo_path(subtree)
    git(repo, "rev-parse", "--git-dir")
    base = resolve_commit(repo, base_ref)
    candidate = resolve_commit(repo, candidate_ref)
    left = entries_at(repo, base, subtree)
    right = entries_at(repo, candidate, subtree)
    changes = []
    for path in sorted(left.keys() | right.keys()):
        old, new = left.get(path), right.get(path)
        if old == new:
            continue
        status = "added" if old is None else "removed" if new is None else "modified"
        changes.append({"path": path, "status": status, "base": old, "candidate": new})
    return {
        "schema": SCHEMA,
        "tool_version": VERSION,
        "comparison_id": f"checkout-compare-{base[:12]}-{candidate[:12]}-{subtree.replace('/', '_')}",
        "repository": str(repo),
        "path_scope": subtree,
        "base_commit": base,
        "candidate_commit": candidate,
        "changed_file_count": len(changes),
        "changes": changes,
        "sensitive_paths_omitted": True,
        "working_tree_modified": False,
        "network_used": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=".", help="existing local Git repository")
    parser.add_argument("--base", required=True, help="base commit, tag, or branch")
    parser.add_argument("--candidate", required=True, help="candidate commit, tag, or branch")
    parser.add_argument("--path", required=True, help="repository-relative Checkout source path")
    args = parser.parse_args(argv)
    try:
        result = compare(Path(args.repo), args.base, args.candidate, args.path)
    except (CompareError, OSError, ValueError) as exc:
        print(json.dumps({"schema": SCHEMA, "tool_version": VERSION, "error": str(exc)}, indent=2))
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
