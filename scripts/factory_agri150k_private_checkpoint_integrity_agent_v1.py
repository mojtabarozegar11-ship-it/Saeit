#!/usr/bin/env python3
"""Read-only, fail-closed AGRI-001 PRIVATE_QA checkpoint integrity agent.

Audits content hashes, gate-v1 mechanical counts, inventory binding and
sampled cross-chunk repetition. It cannot approve scientific QC or publish.
No manuscript text or private absolute path is emitted.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat

CHUNK = re.compile(r"chapter-(\d{2})-part-(\d{3})\.md\Z")
SCHEMA = re.compile(r"saeit\.agri150k\.private-draft-checkpoint\.v[1-9]\d*\Z")
MAX_CHUNK_BYTES = 240_000
MAX_MANIFEST_BYTES = 120_000


class IntegrityBlocked(ValueError):
    """Fail closed; no release authorization is ever generated."""


def _read_regular(path: Path, *, limit: int) -> bytes:
    if path.is_symlink():
        raise IntegrityBlocked("UNSAFE_SYMLINK")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        meta = os.fstat(fd)
        if not stat.S_ISREG(meta.st_mode) or not 0 < meta.st_size <= limit:
            raise IntegrityBlocked("UNSAFE_FILE_SIZE_OR_TYPE")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            data = stream.read(limit + 1)
        if len(data) != meta.st_size:
            raise IntegrityBlocked("FILE_CHANGED_DURING_READ")
        return data
    finally:
        os.close(fd)


WORD = re.compile(r"[^\W\d_][\w’'-]*", re.UNICODE)


def prose_tokens(markdown):
    """Byte-for-byte equivalent tokenization contract to AGRI gate-v1."""
    lines = []
    fenced = False
    references = False
    for raw in markdown.splitlines():
        s = raw.strip()
        if s.startswith(("~~~", chr(96) * 3)):
            fenced = not fenced
            continue
        if fenced or not s:
            continue
        if s.startswith("#"):
            if re.match(r"^#{1,6}\s+(references|bibliography|sources|works cited)\b", s, re.I):
                references = True
            continue
        if references or s.startswith((">", "|", "http://", "https://")):
            continue
        s = re.sub(r"https?://\S+", " ", s)
        s = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", s)
        lines.append(s)
    return [m.group().casefold() for m in WORD.finditer(" ".join(lines))]


def audit(private_dir: Path) -> dict:
    root = Path(private_dir)
    if root.is_symlink() or not root.is_dir():
        raise IntegrityBlocked("PRIVATE_ROOT_NOT_SAFE")
    root = root.resolve(strict=True)
    raw_manifest = _read_regular(root / "manifest.json", limit=MAX_MANIFEST_BYTES)
    try:
        manifest = json.loads(raw_manifest)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise IntegrityBlocked("MANIFEST_INVALID_JSON") from exc
    if not isinstance(manifest, dict) or not SCHEMA.fullmatch(str(manifest.get("schema", ""))):
        raise IntegrityBlocked("MANIFEST_SCHEMA_INVALID")
    if (manifest.get("product_id") != "AGRI-001"
            or manifest.get("title") != "Houseplant Rescue Guide"
            or manifest.get("language") != "en-US"
            or manifest.get("publication_allowed") is not False
            or manifest.get("qc1000_approved") is not False
            or manifest.get("independent_scientific_review") is not False):
        raise IntegrityBlocked("PRIVATE_RELEASE_GATES_INVALID")
    chunks = manifest.get("chunks")
    if not isinstance(chunks, list) or not chunks:
        raise IntegrityBlocked("NO_CHECKPOINT_CHUNKS")
    actual = {p.name for p in root.glob("chapter-??-part-???.md")}
    declared = set()
    previous = set()
    total = 0
    count_by_chapter = {}
    for row in chunks:
        if not isinstance(row, dict):
            raise IntegrityBlocked("CHUNK_RECORD_INVALID")
        name = row.get("file")
        match = CHUNK.fullmatch(name) if isinstance(name, str) else None
        if match is None or name in declared:
            raise IntegrityBlocked("CHUNK_NAME_OR_DUPLICATE_INVALID")
        chapter, part = int(match.group(1)), int(match.group(2))
        if (row.get("chapter"), row.get("part")) != (chapter, part):
            raise IntegrityBlocked("CHUNK_NUMBER_BINDING_INVALID")
        if (not 1 <= chapter <= 30 or part < 1
                or row.get("publication_allowed") is not False
                or row.get("qc1000_approved") is not False
                or row.get("independent_scientific_review") is not False):
            raise IntegrityBlocked("CHUNK_PRIVATE_GATES_INVALID")
        raw = _read_regular(root / name, limit=MAX_CHUNK_BYTES)
        digest = hashlib.sha256(raw).hexdigest()
        if row.get("sha256") != digest or row.get("bytes") != len(raw):
            raise IntegrityBlocked("CHUNK_SHA256_OR_LENGTH_MISMATCH")
        try:
            tokens = prose_tokens(raw.decode("utf-8"))
        except UnicodeDecodeError as exc:
            raise IntegrityBlocked("CHUNK_NOT_UTF8") from exc
        count = len(tokens)
        if (count != row.get("mechanical_prose_words_unreviewed_gate_v1")
                or not 600 <= count <= 4500 or len(set(tokens)) < 120):
            raise IntegrityBlocked("CHUNK_MECHANICAL_WORDS_INVALID")
        shingles = [tuple(tokens[i:i + 12]) for i in range(0, len(tokens) - 11, 6)]
        if (not shingles or len(set(shingles)) / len(shingles) < .85
                or previous and sum(sh in previous for sh in shingles) / len(shingles) > .10):
            raise IntegrityBlocked("CHUNK_REPETITION_OVERLAP")
        previous.update(tuple(tokens[i:i + 12]) for i in range(0, len(tokens) - 11, 3))
        total += count
        count_by_chapter[chapter] = count_by_chapter.get(chapter, 0) + count
        declared.add(name)
    if actual != declared:
        raise IntegrityBlocked("UNTRACKED_OR_MISSING_CHUNK")
    if manifest.get("mechanical_prose_words_unreviewed_gate_v1") != total:
        raise IntegrityBlocked("MANIFEST_TOTAL_MISMATCH")
    return {
        "schema": "saeit.agri150k.private-integrity-agent.v1",
        "product_id": "AGRI-001",
        "state": "PRIVATE_QA_MECHANICAL_INTEGRITY_ONLY",
        "manifest_sha256": hashlib.sha256(raw_manifest).hexdigest(),
        "chunks_checked": len(chunks),
        "unreviewed_mechanical_words": total,
        "chapter_mechanical_words": count_by_chapter,
        "hash_count_inventory_novelty_checks": "PASS",
        "independent_scientific_review": False,
        "qc1000_approved": False,
        "publication_allowed": False,
        "private_text_emitted": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--private-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = audit(args.private_dir)
    except (IntegrityBlocked, OSError, TypeError, ValueError) as exc:
        print(json.dumps({"schema": "saeit.agri150k.private-integrity-agent.v1",
                          "state": "BLOCKED", "reason": str(exc),
                          "publication_allowed": False,
                          "private_text_emitted": False}, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
