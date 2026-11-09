"""Read-only, fail-closed preflight for a narrowly scoped newsroom release.

Never installs, replaces, deletes, chmods or backs up files. This scanner
compares the target app's existing files against an immutable GitHub blob
manifest for PR #2194. It explicitly rejects unsafe paths and symlinks.
"""

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys


def git_blob_sha(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def _safe_path(relative: str) -> PurePosixPath:
    if not isinstance(relative, str) or not relative.startswith("core/"):
        raise ValueError("Manifest file must be under core/")
    candidate = PurePosixPath(relative)
    if candidate.is_absolute() or ".." in candidate.parts or "." in candidate.parts:
        raise ValueError("Unsafe manifest path")
    if any(not part or part.startswith(".") for part in candidate.parts):
        raise ValueError("Hidden or empty path component")
    return candidate


def inspect_release(root: Path, manifest: dict) -> dict:
    """Inspect without file writes and without following existing symlinks."""
    if manifest.get("version") != 1 or manifest.get("mode") != "READ_ONLY_PREFLIGHT":
        raise ValueError("Unknown or unsafe manifest version")
    if not root.is_dir() or root.is_symlink():
        raise ValueError("Target must be an existing, non-symlink app directory")
    if root.resolve() == Path("/"):
        raise ValueError("Filesystem root cannot be a target")
    rows = []
    seen = set()
    for entry in manifest.get("files", []):
        part = _safe_path(entry.get("path"))
        name = str(part)
        if name in seen:
            raise ValueError("Duplicate manifest path")
        seen.add(name)
        expected = entry.get("git_blob_sha", "")
        if not isinstance(expected, str) or len(expected) != 40 or any(c not in "0123456789abcdef" for c in expected):
            raise ValueError("Invalid Git blob SHA")
        change = entry.get("change")
        if change not in {"added", "modified"}:
            raise ValueError("Unknown change type")

        path = root.joinpath(*part.parts)
        parents = [root.joinpath(*part.parts[:n]) for n in range(1, len(part.parts))]
        if any(p.is_symlink() for p in parents) or path.is_symlink():
            status = "unsafe_symlink"
            actual = None
        elif not path.exists():
            status = "new_file_missing" if change == "added" else "modified_file_missing"
            actual = None
        elif not path.is_file():
            status = "unsafe_not_regular_file"
            actual = None
        else:
            try:
                actual = git_blob_sha(path.read_bytes())
                status = "already_current" if actual == expected else "different_manual_merge_required"
            except OSError:
                status = "unreadable"
                actual = None
        rows.append({"path": name, "change": change, "state": status, "actual_git_blob_sha": actual})

    counts = {state: sum(r["state"] == state for r in rows) for state in sorted({r["state"] for r in rows})}
    unsafe = sum(v for k, v in counts.items() if k not in {"already_current", "new_file_missing"})
    return {
        "mode": "READ_ONLY_PREFLIGHT",
        "repository": manifest.get("repository"),
        "commit": manifest.get("commit"),
        "files_scanned": len(rows),
        "counts": counts,
        "requires_manual_reconciliation": bool(unsafe),
        "safe_to_apply_automatically": False,
        "entries": rows,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Inspect newsroom release files; never modify the host")
    parser.add_argument("--target-root", required=True, type=Path)
    parser.add_argument("--manifest", type=Path, default=Path(__file__).with_name("newsroom_release_manifest_20261108.json"))
    parser.add_argument("--strict", action="store_true", help="Nonzero exit for conflicting or missing modified files")
    args = parser.parse_args(argv)
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        result = inspect_release(args.target_root, manifest)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "blocked", "reason": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 2 if args.strict and result["requires_manual_reconciliation"] else 0


if __name__ == "__main__":
    sys.exit(main())
