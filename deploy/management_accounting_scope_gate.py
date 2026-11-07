#!/usr/bin/env python3
"""Validate a management/accounting-only SOURCE bundle without side effects.

This is not a production release gate. It verifies that a fixed seven-file
runtime allowlist matches reviewed Git blob hashes; it cannot attest cPanel
interpreter identity, database migration state, recoverable backups or rollback.
It never invokes Django, opens a database, deploys, restarts or sends messages.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import stat


SCHEMA = "saeit-management-accounting-runtime-scope-v1"
RUNTIME_FILES = (
    "accounting/admin.py",
    "accounting/services.py",
    "command_center/integrated_ledger_api.py",
    "command_center/management/__init__.py",
    "command_center/management/commands/__init__.py",
    "command_center/management/commands/audit_management_cycles.py",
    "command_center/templates/command_center/integrated_dashboard.html",
)


def git_blob_sha1(data: bytes) -> str:
    """Match Git's content-addressed SHA-1 over a blob, not a raw file SHA-1."""
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def audit_scope(root: pathlib.Path, manifest: dict) -> dict:
    issues: list[str] = []
    if not isinstance(manifest, dict):
        return _result(["manifest_not_object"])
    if manifest.get("schema") != SCHEMA:
        issues.append("unsupported_schema")
    if manifest.get("production_release_permitted") is not False:
        issues.append("release_flag_must_be_false")
    rows = manifest.get("runtime_files")
    if not isinstance(rows, list) or any(not isinstance(x, dict) for x in rows):
        return _result(issues + ["invalid_runtime_files"])
    paths = [x.get("path") for x in rows]
    if len(paths) != len(set(p for p in paths if isinstance(p, str))):
        issues.append("duplicate_runtime_path")
    if len(rows) != len(RUNTIME_FILES) or set(p for p in paths if isinstance(p, str)) != set(RUNTIME_FILES):
        issues.append("runtime_allowlist_mismatch")
    if any(set(x) != {"path", "git_blob_sha1", "sha256"} for x in rows):
        issues.append("unexpected_manifest_fields")
    if root.is_symlink() or not root.is_dir():
        return _result(issues + ["invalid_source_root"])

    # Read ONLY the hard-coded allowlist, never arbitrary manifest paths.
    rows_by_path = {x.get("path"): x for x in rows if isinstance(x.get("path"), str)}
    for relative in RUNTIME_FILES:
        entry = rows_by_path.get(relative, {})
        wanted = entry.get("git_blob_sha1")
        wanted_sha256 = entry.get("sha256")
        if not isinstance(wanted, str) or not re.fullmatch(r"[0-9a-f]{40}", wanted):
            issues.append("missing_or_invalid_hash:" + relative)
            continue
        if not isinstance(wanted_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", wanted_sha256):
            issues.append("missing_or_invalid_sha256:" + relative)
            continue
        current = root
        components = pathlib.PurePosixPath(relative).parts
        blocked = False
        for component in components:
            current = current / component
            if current.is_symlink():
                blocked = True
                break
        if blocked:
            issues.append("symlink_not_allowed:" + relative)
            continue
        try:
            if not stat.S_ISREG(current.stat().st_mode):
                issues.append("not_regular_file:" + relative)
                continue
            data = current.read_bytes()
            actual = git_blob_sha1(data)
            actual_sha256 = hashlib.sha256(data).hexdigest()
        except OSError:
            issues.append("unreadable_or_missing:" + relative)
            continue
        if actual != wanted:
            issues.append("content_hash_mismatch:" + relative)
        if actual_sha256 != wanted_sha256:
            issues.append("content_sha256_mismatch:" + relative)
    return _result(issues)


def _result(issues: list[str]) -> dict:
    return {
        "classification": "MANAGEMENT_ACCOUNTING_SOURCE_SCOPE_ONLY",
        "source_scope_verified": not issues,
        "runtime_file_count": len(RUNTIME_FILES),
        "issues": issues,
        "production_release_permitted": False,
        "live_interpreter_attested": False,
        "production_migrations_attested": False,
        "backup_restore_attested": False,
        "scoped_rollback_attested": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=pathlib.Path, default=pathlib.Path(__file__).resolve().parents[1])
    parser.add_argument("--manifest", type=pathlib.Path, default=pathlib.Path(__file__).with_name("management_accounting_scope.json"))
    args = parser.parse_args()
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        result = audit_scope(args.root, manifest)
    except (OSError, ValueError, UnicodeError, json.JSONDecodeError):
        result = _result(["unreadable_or_invalid_manifest"])
    print(json.dumps(result, sort_keys=True, ensure_ascii=False))
    return 0 if result["source_scope_verified"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
