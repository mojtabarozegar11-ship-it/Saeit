#!/usr/bin/env python3
"""READ ONLY on-host MojPlayWin rewrite and legacy-backup evidence.

This is a limited metadata inspection, never an isolation or restore proof.
It does NOT invoke Django or cPanel, start/restart Passenger, access customer
data, alter permissions, write files or display private configuration text.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

DOCROOT = Path("/home/zomorod2/mojplaywin.com")
BACKUP_ROOT = Path("/home/zomorod2/.mojplaywin-backups")
KNOWN = ("mojtaba.roozegar", "picm", "studio.Roham", "saman", "zahra$$", "farnaz", "taniya")
MAX_SOURCE_BYTES = 256_000
MAX_MANIFEST_BYTES = 128_000


def safe_read(file: Path, max_bytes: int) -> str | None:
    try:
        if file.is_symlink() or not file.is_file():
            return None
        if file.stat().st_size > max_bytes:
            return None
        return file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def summarize_rewrites(source: str | None) -> dict:
    if source is None:
        return {
            "htaccess_readable": False, "rewriterule_count": None,
            "rewritecond_count": None, "passenger_directive_count": None,
            "explicit_prefix_mentions": {name: None for name in KNOWN},
            "catch_all_patterns_present": None,
        }
    lines = source.splitlines()
    rule_lines = [ln.strip() for ln in lines
                  if re.match(r"^\s*RewriteRule\s+", ln, flags=re.I)]
    condition_lines = [ln for ln in lines
                       if re.match(r"^\s*RewriteCond\s+", ln, flags=re.I)]
    passengers = [ln for ln in lines
                  if re.match(r"^\s*Passenger[A-Za-z]+\b", ln, flags=re.I)]
    catch_all = any(
        re.search(r"(?i)^RewriteRule\s+(?:\^/?\.?\*|\^/?\(\.\*\)|\^/?\(\.\+\)|\(\.\*\))", ln)
        for ln in rule_lines
    )
    # Prefix mentions are lexical evidence ONLY, not proof of actual precedence.
    return {
        "htaccess_readable": True,
        "rewriterule_count": len(rule_lines),
        "rewritecond_count": len(condition_lines),
        "passenger_directive_count": len(passengers),
        "explicit_prefix_mentions": {
            name: name.lower() in source.lower() for name in KNOWN
        },
        "catch_all_patterns_present": catch_all,
    }


def summarize_backups(root: Path = BACKUP_ROOT) -> dict:
    result = {
        "legacy_backup_root_directory_exists": root.is_dir() and not root.is_symlink(),
        "legacy_backup_directory_count": 0,
        "legacy_manifest_found_count": 0,
        "legacy_deployment_marker_count": 0,
        "legacy_rollback_marker_count": 0,
        "legacy_manifests_with_database_path": 0,
        "legacy_manifests_with_media_path": 0,
        "legacy_manifests_unreadable_or_invalid": 0,
        "inspection_complete": False,
        "database_backup_verified": False,
        "media_backup_verified": False,
        "restore_test_verified": False,
    }
    if not result["legacy_backup_root_directory_exists"]:
        return result
    try:
        # Never follow links, list only expected legacy deploy folders;
        # no backup content, filenames or run identifiers leave the server.
        entries = sorted(
            (p for p in root.iterdir()
             if p.name.startswith("mojplaywin-main-") and p.is_dir() and not p.is_symlink()),
            key=lambda p: p.name
        )
        if len(entries) > 500:
            return result
        for backup in entries:
            result["legacy_backup_directory_count"] += 1
            raw = safe_read(backup / "manifest.json", MAX_MANIFEST_BYTES)
            if raw is None:
                result["legacy_manifests_unreadable_or_invalid"] += 1
                continue
            try:
                manifest = json.loads(raw)
                if not isinstance(manifest, dict):
                    raise ValueError("invalid manifest type")
            except (ValueError, TypeError):
                result["legacy_manifests_unreadable_or_invalid"] += 1
                continue
            result["legacy_manifest_found_count"] += 1
            paths = [str(k).lower().strip("/") for k in manifest.keys()]
            if any(p.endswith((".sqlite3", ".sqlite", ".db", ".sql", ".sql.gz")) for p in paths):
                result["legacy_manifests_with_database_path"] += 1
            if any(p.startswith("media/") or "/media/" in p for p in paths):
                result["legacy_manifests_with_media_path"] += 1
            if (backup / "DEPLOYED.json").is_file() and not (backup / "DEPLOYED.json").is_symlink():
                result["legacy_deployment_marker_count"] += 1
            if (backup / "ROLLED_BACK").is_file() and not (backup / "ROLLED_BACK").is_symlink():
                result["legacy_rollback_marker_count"] += 1
        result["inspection_complete"] = True
    except OSError:
        pass
    return result


def audit(docroot: Path = DOCROOT, backups: Path = BACKUP_ROOT) -> dict:
    source = safe_read(docroot / ".htaccess", MAX_SOURCE_BYTES)
    return {
        "classification": "READ_ONLY_REWRITE_AND_LEGACY_BACKUP_METADATA",
        "rewrite": summarize_rewrites(source),
        "legacy_backups": summarize_backups(backups),
        "warnings": [
            "Rewrite lexical counts cannot prove effective vhost routing or protection of unknown child sites.",
            "Legacy deployment manifests are NOT verified full database/media backups.",
            "An existing backup is NOT a verified successful restore.",
        ],
        "all_subsites_inventoried": False,
        "production_isolation_proven": False,
        "restore_test_verified": False,
        "release_permitted": False,
    }


if __name__ == "__main__":
    print(json.dumps(audit(), sort_keys=True, ensure_ascii=False))
