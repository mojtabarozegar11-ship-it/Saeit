#!/usr/bin/env python3
"""Fail-closed policy gate for MojPlayWin backup source changes.

This is a static source check. It never connects to cPanel, reads secrets,
creates backups, deletes files, or changes production. The only permitted
production database backup path is the stream-to-offhost implementation.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

TEXT_EXTENSIONS = {".py", ".sh", ".yml", ".yaml"}
LEGACY_DISABLED = Path(".github/workflows/zomorod-live-mysql-precompression-backup.yml")

# These patterns describe a local SQL artifact, not a harmless SQL argument
# sent to a client. The gate deliberately reports only file names and fixed
# policy categories.
LOCAL_SQL_OUTPUT = (
    re.compile(r"(?i)Saeit-staging[/\\]backups[^\n#]*\.sql(?:\.gz)?"),
    re.compile(r"(?i)(?:out|tmp|target|dest|output|dump_path|backup_path)\s*=\s*[^\n#]*(?:\.sql(?:\.gz)?|\.sql\.partial)"),
    re.compile(r"(?i)(?:open|gzip\.open)\s*\([^\n)]*\.sql(?:\.gz)?"),
    re.compile(r"(?i)>\s*[^\n#]*(?:\.sql(?:\.gz)?|Saeit-staging[/\\]backups)"),
    re.compile(r"(?i)mojprop-prepromotion-db"),
)

def is_source_file(path: Path) -> bool:
    return path.suffix.casefold() in TEXT_EXTENSIONS

def legacy_is_fail_closed(text: str) -> bool:
    return bool(re.search(r"(?m)^\s*if:\s*false\s*$", text))

def inspect(path: Path) -> list[str]:
    if not is_source_file(path):
        return []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ["POLICY_FILE_UNREADABLE"]
    # Do not lint this gate against its own detection patterns.
    if path.name == Path(__file__).name and path.resolve() == Path(__file__).resolve():
        return []
    if path == LEGACY_DISABLED:
        return [] if legacy_is_fail_closed(text) else ["LEGACY_PRECOMPRESSION_NOT_DISABLED"]
    findings: list[str] = []
    for pattern in LOCAL_SQL_OUTPUT:
        if pattern.search(text):
            findings.append("LOCAL_SQL_ARTIFACT_OUTPUT")
            break
    if path.name == "mojplaywin_backup_stream_cpanel.py":
        if "sys.stdout.buffer.write" not in text or "BACKUP_SOURCE_STREAM_COMPLETED" not in text:
            findings.append("STREAM_IMPLEMENTATION_CONTRACT_MISSING")
    return findings

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
    print("LOCAL_SQL_ARTIFACTS=FORBIDDEN")
    print("PRODUCTION_BACKUP_MODE=STREAM_TO_OFFHOST")
    print("LEGACY_PRECOMPRESSION=DISABLED_REQUIRED")
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
