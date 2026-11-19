#!/usr/bin/env python3
"""Fail-closed policy gate for MojPlayWin backup source changes.

This static check never connects to cPanel, reads secrets, creates backups,
deletes files, or changes production. It blocks only the historical MojProp
raw-SQL staging path; unrelated factory/robot backup workflows are separate.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

TEXT_EXTENSIONS = {".py", ".sh", ".yml", ".yaml"}
LEGACY_NAME = "zomorod-live-mysql-precompression-backup.yml"

# Scope is deliberately narrow: these are the exact historical artifacts that
# exhausted the MojPlayWin cPanel quota. SQL arguments for other databases are
# not blocked by this gate.
LOCAL_SQL_OUTPUT = (
    re.compile(r"(?i)Saeit-staging[/\\]backups"),
    re.compile(r"(?i)mojprop-prepromotion-db"),
)

def is_source_file(path: Path) -> bool:
    return path.suffix.casefold() in TEXT_EXTENSIONS

def is_legacy_path(path: Path) -> bool:
    return path.name == LEGACY_NAME

def legacy_is_fail_closed(text: str) -> bool:
    return bool(re.search(r"(?m)^\s*if:\s*false\s*$", text))

def inspect(path: Path) -> list[str]:
    if not is_source_file(path):
        return []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ["POLICY_FILE_UNREADABLE"]
    if path.name == "mpw_backup_policy_gate.py":
        return []
    if is_legacy_path(path):
        return [] if legacy_is_fail_closed(text) else ["LEGACY_PRECOMPRESSION_NOT_DISABLED"]
    for pattern in LOCAL_SQL_OUTPUT:
        if pattern.search(text):
            return ["LOCAL_MOJPROP_SQL_STAGING_PATH"]
    if path.name == "mojplaywin_backup_stream_cpanel.py":
        if "sys.stdout.buffer.write" not in text or "BACKUP_SOURCE_STREAM_COMPLETED" not in text:
            return ["STREAM_IMPLEMENTATION_CONTRACT_MISSING"]
    return []

def main(argv: list[str]) -> int:
    paths = [Path(item) for item in argv[1:]]
    if not paths:
        paths = [Path(".github/workflows"), Path("scripts")]
    files: list[Path] = []
    for path in paths:
        if path.is_file():
            files.append(path)
        elif path.is_dir():
            files.extend(item for item in path.rglob("*") if item.is_file())
    violations: list[tuple[str, str]] = []
    for path in sorted(set(files)):
        for finding in inspect(path):
            violations.append((str(path), finding))
    if violations:
        for path, finding in violations:
            print(f"BACKUP_POLICY=FAIL file={path} category={finding}")
        return 1
    print("BACKUP_POLICY=PASS")
    print("LOCAL_MOJPROP_SQL_STAGING=FORBIDDEN")
    print("PRODUCTION_BACKUP_MODE=STREAM_TO_OFFHOST")
    print("LEGACY_PRECOMPRESSION=DISABLED_REQUIRED")
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
