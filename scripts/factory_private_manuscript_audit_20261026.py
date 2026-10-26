#!/usr/bin/env python3
"""Read-only, fail-closed private manuscript length and integrity audit.

This is NOT scientific peer review, originality certification or permission to publish.
No manuscript files, locks, crons or storefront data are modified.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import unicodedata

PART = re.compile(r"chapter-(\d{2})-part-(\d{3})\.md\Z")
WORD = re.compile(r"[A-Za-z][A-Za-z'-]*")
FORBIDDEN = ("<think", "</think", "<|im_start|>", "<|im_end|>",
             "<|assistant", "<|endoftext|>", "[inst]", "[/inst]",
             "lorem ipsum", "[citation needed]", "as an ai language model")
MAX_SEGMENT_BYTES = 50000


def normalize_similarity_text(text: str) -> str:
    """Canonicalize visually identical English prose for duplicate checks.

    Formatting controls and compatibility glyphs must not let copied text
    evade the private QC gate. This affects hashes only, never source files,
    substantive word counts, or scientific identifiers with underscores.
    """
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"[\u00ad\u200b\u200c\u200d\u2060\ufeff\u202a-\u202e\u2066-\u2069]", "", text)
    text = re.sub(r"[*\x60]|(?<!\w)_+|_+(?!\w)", "", text)
    return re.sub(r"\s+", " ", text).strip()


def substantive_words(text: str) -> list[str]:
    lines = []
    for row in text.splitlines():
        row = row.strip()
        if not row or row.startswith(("#", "|", "http://", "https://")):
            continue
        lines.append(re.sub(r"https?://\S+", "", row))
    return [x.casefold() for x in WORD.findall("\n".join(lines))]


def audit(root: Path, *, chapters: int = 30, chapter_target: int = 5300,
          total_target: int = 159000) -> dict:
    """Produce private evidence hashes and structural diagnostics; never approve release."""
    if not 1 <= chapters <= 99 or chapter_target <= 0 or total_target <= 0:
        raise ValueError("invalid audit target")
    if root.is_symlink() or not root.is_dir():
        raise ValueError("unsafe or absent manuscript directory")
    counts = {str(i): 0 for i in range(1, chapters + 1)}
    parts = {i: [] for i in range(1, chapters + 1)}
    hashes = []
    flags = []
    seen_segment_hashes = {}  # Detect exact repeated manuscript segments across chapters.
    seen_prose_hashes = {}  # Catch copied bodies with changed headings or whitespace.
    seen_long_paragraphs = {}  # Catch reused long paragraphs in otherwise different parts.
    total = 0
    for path in sorted(root.iterdir()):
        if path.name in ("status.json", "complete-unreviewed.md", ".authoring.lock"):
            continue
        if path.name.startswith(".leech-status-"):
            continue  # atomic status writer temporary file, never prose
        match = PART.fullmatch(path.name)
        if not match or path.is_symlink() or not path.is_file():
            flags.append("unexpected_or_unsafe_entry:" + path.name[:80])
            continue
        chapter, part = map(int, match.groups())
        if chapter not in parts or not 1 <= part <= 999:
            flags.append("out_of_range_part:" + path.name)
            continue
        size = path.stat().st_size
        if not 200 < size <= MAX_SEGMENT_BYTES:
            flags.append("invalid_segment_size:" + path.name)
            continue
        raw = path.read_bytes()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            flags.append("invalid_utf8:" + path.name)
            continue
        # Normalize only for the safety check; never modify manuscript bytes.
        # Unicode format controls and compatibility glyphs must not conceal
        # reasoning tokens or unverified citation placeholders.
        if any(token in normalize_similarity_text(text).casefold() for token in FORBIDDEN):
            flags.append("unsafe_content_marker:" + path.name)
        digest = hashlib.sha256(raw).hexdigest()
        first_path = seen_segment_hashes.setdefault(digest, path.name)
        if first_path != path.name:
            flags.append("duplicate_segment_content:" + path.name + ":" + first_path)
        # Headings and spacing must not conceal duplicated substantive prose.
        # Fail closed on long identical bodies; keep this a mechanical gate only.
        prose = " ".join(
            re.sub(r"\s+", " ", row.strip()).casefold()
            for row in text.splitlines()
            if row.strip() and not row.lstrip().startswith("#")
        ).strip()
        # Strip Markdown emphasis/backticks even within words, but retain
        # underscores between identifier characters (term_0000 != term0000).
        prose = normalize_similarity_text(prose)
        if len(prose) >= 500:
            prose_hash = hashlib.sha256(prose.encode("utf-8")).hexdigest()
            first_prose = seen_prose_hashes.setdefault(prose_hash, path.name)
            if first_prose != path.name and first_path == path.name:
                flags.append("duplicate_prose_body:" + path.name + ":" + first_prose)
        # An altered introduction or conclusion must not hide an otherwise
        # identical substantial paragraph. Keep only hashes and private names;
        # no manuscript prose is emitted in the evidence.
        for paragraph_index, paragraph in enumerate(
                re.split(r"\n[ \t]*\n", text), 1):
            body = " ".join(line for line in paragraph.splitlines()
                            if line.strip() and not line.lstrip().startswith("#"))
            # Match the full-prose gate: inline emphasis must not split tokens.
            # Preserve underscores inside identifiers (term_0000 != term0000).
            body = normalize_similarity_text(body)
            tokens = [word.casefold() for word in
                      re.findall(r"[A-Za-z][A-Za-z0-9_'-]*", body)]
            if len(tokens) < 100:
                continue
            paragraph_hash = hashlib.sha256(
                " ".join(tokens).encode("utf-8")).hexdigest()
            origin = seen_long_paragraphs.setdefault(
                paragraph_hash, f"{path.name}:paragraph-{paragraph_index}")
            location = f"{path.name}:paragraph-{paragraph_index}"
            if origin != location:
                flags.append("duplicate_long_paragraph:" + location + ":" + origin)
        n = len(substantive_words(text))
        counts[str(chapter)] += n
        total += n
        parts[chapter].append(part)
        hashes.append({"name": path.name, "sha256": digest,
                       "substantive_words": n})
    for chapter, numbers in parts.items():
        if sorted(numbers) != list(range(1, len(numbers) + 1)):
            flags.append("noncontiguous_parts:chapter-%02d" % chapter)
    missing = [i for i in range(1, chapters + 1) if counts[str(i)] < chapter_target]
    ready = total >= total_target and not missing and not flags
    return {"schema": "saeit.private.manuscript-integrity-audit.v1",
            "total_substantive_words": total, "target_words": total_target,
            "chapter_word_counts": counts, "chapters_below_target": missing,
            "part_evidence": hashes, "integrity_flags": flags,
            "length_and_structure_ready_for_independent_review": ready,
            "independent_scientific_review_passed": False,
            "quality1000_approved": False, "commercial_release_allowed": False,
            "manuscript_modified": False}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manuscript-dir", type=Path, required=True)
    parser.add_argument("--chapters", type=int, default=30)
    parser.add_argument("--chapter-target", type=int, default=5300)
    parser.add_argument("--total-target", type=int, default=159000)
    args = parser.parse_args()
    try:
        print(json.dumps(audit(args.manuscript_dir, chapters=args.chapters,
                               chapter_target=args.chapter_target,
                               total_target=args.total_target), sort_keys=True))
    except (OSError, ValueError) as exc:
        parser.exit(2, "MANUSCRIPT_AUDIT_BLOCKED: " + str(exc)[:160] + "\n")


if __name__ == "__main__":
    main()
