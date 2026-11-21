#!/usr/bin/env python3
"""Deterministic, source-only game candidate archive; never deploys or accesses secrets."""
from __future__ import annotations
import hashlib
import json
import os
import sys
import zipfile
from pathlib import Path

FILES = (
    "games/ramadan-war/game.js",
    "games/ramadan-war/game.css",
    "games/ramadan-war/index.html",
    "games/crown-defender/index.html",
    "templates/studio_raha/index.html",
    "templates/taniya_studio/index.html",
    "site_releases/mojplaywin/games-20261021/beacon-labyrinth/index.html",
    "site_releases/mojplaywin/games-20261021/nebula-salvage/index.html",
)

def info(data: bytes, path: str) -> dict:
    return {"path": path, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}

def build(target: Path, root: Path = Path(".")) -> dict:
    records = []
    payloads = []
    for relative in FILES:
        source = root / relative
        if not source.is_file() or source.is_symlink():
            raise ValueError("Missing or unsafe game source: " + relative)
        data = source.read_bytes()
        if len(data) > 500_000:
            raise ValueError("Unexpectedly large source: " + relative)
        records.append(info(data, relative))
        payloads.append((relative, data))
    manifest = {"schema": 1, "type": "source-only-candidate-not-production-backup",
                "commit": os.environ.get("GITHUB_SHA", "local"), "files": records}
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in payloads + [("MANIFEST.json", json.dumps(manifest, sort_keys=True, indent=2).encode("utf-8"))]:
            entry = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o644 << 16
            archive.writestr(entry, data)
    verify(target)
    return manifest

def verify(target: Path) -> None:
    with zipfile.ZipFile(target) as archive:
        manifest = json.loads(archive.read("MANIFEST.json"))
        expected = {row["path"]: row for row in manifest["files"]}
        if set(archive.namelist()) != set(expected) | {"MANIFEST.json"}:
            raise ValueError("Archive includes unexpected or missing files")
        if set(expected) != set(FILES):
            raise ValueError("Candidate manifest has changed scope")
        for name, row in expected.items():
            if info(archive.read(name), name) != row:
                raise ValueError("Candidate checksum mismatch: " + name)

if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in {"build", "verify"}:
        raise SystemExit("Usage: game_candidate_packager.py build|verify /path/to/archive.zip")
    archive_path = Path(sys.argv[2])
    if sys.argv[1] == "build":
        result = build(archive_path)
        print("GAME_SOURCE_CANDIDATE_BUILT=PASS files=", len(result["files"]), "sha=", result["commit"])
    else:
        verify(archive_path)
        print("GAME_SOURCE_CANDIDATE_VERIFIED=PASS")
