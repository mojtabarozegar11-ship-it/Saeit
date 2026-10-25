#!/usr/bin/env python3
"""Zero-external-inference-charge, source-scoped private leech manuscript builder.

GitHub public runner performs CPU-only offline inference; this VPS-side worker
only validates inputs and privately accepts original prose. No API, payment,
site publication, checkout, customer data, review impersonation or release.
"""
from __future__ import annotations
import argparse
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile

ORDER = "WO-26102501"
PRODUCT = "vocational-leech-farming-en-20261025"
REQUIRED_CHAPTERS = 30
MIN_WORDS = 150001
TARGET_PER_CHAPTER = 5300
PART = re.compile(r"chapter-(\d{2})-part-(\d{3})\.md\Z")
WORD = re.compile(r"[A-Za-z][A-Za-z'-]*")
ROOT = Path("/home/githubops/factory-runtime/private/autonomous-product-cycle")
AREA = ROOT / "production-instructions"
PRIVATE = AREA / "stage-04/original-manuscript" / ORDER
NAME = ORDER + "--r001.json"

def reject(message):
    raise RuntimeError("LEECH_ZERO_COST_" + message)

def digest(doc):
    return hashlib.sha256(json.dumps(doc, sort_keys=True, ensure_ascii=False,
        separators=(",", ":")).encode("utf-8")).hexdigest()

def safe_json(path, max_bytes=300000):
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= max_bytes:
        reject("MISSING_OR_UNSAFE_JSON_" + path.name)
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        reject("NOT_JSON_OBJECT")
    return obj

def words(text):
    lines = []
    for row in text.splitlines():
        s = row.strip()
        if s.startswith(("#", "|", "http://", "https://")) or not s:
            continue
        s = re.sub(r"https?://\S+", "", s)
        lines.append(s)
    return [w.casefold() for w in WORD.findall("\n".join(lines))]

def source_evidence():
    order = safe_json(AREA / "orders" / (ORDER + ".json"))
    work = safe_json(AREA / "stage-04/authoring-inbox" / NAME)
    design = safe_json(AREA / "stage-03/completed-designs" / NAME)
    research = safe_json(AREA / "stage-02/completed-dossiers" / NAME)
    extra = safe_json(AREA / "stage-04/primary-research-addenda" / NAME)
    if (order.get("id") != ORDER or order.get("source_product_id") != PRODUCT
       or order.get("publication_approved") is not False
       or work.get("order_id") != ORDER or work.get("source_product_id") != PRODUCT
       or work.get("official_title") != order.get("subject")
       or work.get("minimum_original_manuscript_words") != MIN_WORDS
       or work.get("chapters_queued") != REQUIRED_CHAPTERS
       or work.get("stage3_design_sha256") != digest(design)
       or work.get("stage2_research_sha256") != digest(research)
       or extra.get("stage3_design_sha256") != digest(design)
       or extra.get("stage4_full_authoring_manifest_sha256") != digest(work)
       or work.get("quality1000_approved") is not False
       or work.get("public_distribution_allowed") is not False):
        reject("PROVENANCE_OR_RELEASE_GATE_INVALID")
    chapters = work.get("full_original_chapter_jobs")
    if not isinstance(chapters, list) or len(chapters) != REQUIRED_CHAPTERS:
        reject("CHAPTER_COUNT_INVALID")
    for i, ch in enumerate(chapters, 1):
        if (ch.get("chapter_number") != i or
                ch.get("original_substantive_word_target") != TARGET_PER_CHAPTER or
                ch.get("production_state") != "queued_for_full_original_authorship"):
            reject("CHAPTER_PLAN_INVALID")
    sources = {}
    for e in list(research.get("sources", [])) + list(extra.get("sources", [])):
        if isinstance(e, dict) and isinstance(e.get("id"), str):
            sources[e["id"]] = {"id": e["id"], "title": e.get("title", ""),
                              "url": e.get("url", ""),
                              "limitation": e.get("limited_claim", e.get("evidence_note", ""))}
    if len(sources) < 7:
        reject("SOURCE_MINIMUM_NOT_MET")
    return work, chapters, list(sources.values())

def list_parts():
    chunks = {i: [] for i in range(1, REQUIRED_CHAPTERS + 1)}
    if PRIVATE.is_symlink():
        reject("UNSAFE_PRIVATE_FOLDER")
    if not PRIVATE.exists():
        return chunks
    if not PRIVATE.is_dir():
        reject("PRIVATE_FOLDER_NOT_DIRECTORY")
    for p in sorted(PRIVATE.iterdir()):
        if p.name.startswith(".") or p.name in ("status.json", "complete-unreviewed.md"):
            continue
        match = PART.fullmatch(p.name)
        if not match or p.is_symlink() or not p.is_file() or not 200 < p.stat().st_size <= 50000:
            reject("UNEXPECTED_PRIVATE_MANUSCRIPT_ENTRY")
        chapter, part = map(int, match.groups())
        if not 1 <= chapter <= REQUIRED_CHAPTERS or not 1 <= part <= 999:
            reject("INVALID_CHAPTER_PART_FILENAME")
        text = p.read_text(encoding="utf-8")
        chunks[chapter].append((part, text))
    for chapter, entries in chunks.items():
        if [i for i, _ in entries] != list(range(1, len(entries) + 1)):
            reject("NON_CONTIGUOUS_CHAPTER_PARTS")
    return chunks

def state(chunks):
    counts = {str(i): sum(len(words(x)) for _, x in chunks[i])
              for i in range(1, REQUIRED_CHAPTERS + 1)}
    total = sum(counts.values())
    chapter = next((i for i in range(1, REQUIRED_CHAPTERS + 1)
                    if counts[str(i)] < TARGET_PER_CHAPTER), None)
    part = len(chunks[chapter]) + 1 if chapter else None
    return counts, total, chapter, part

def make_prompt(work, chapters, sources, chunks):
    counts, total, chapter, part = state(chunks)
    if chapter is None:
        return {"complete_length_only": total >= MIN_WORDS, "total_verified_draft_words": total,
                "next_chapter": None, "next_part": None}
    ch = chapters[chapter - 1]
    citation_ids = set(ch.get("research_claim_ids", []))
    # Every chapter may use general foundational sources, but must disclose
    # limits rather than presenting study-level estimates as farm standards.
    accessible = sources[:]
    last_context = "\n\n".join(text for _, text in chunks[chapter])[-1600:]
    return {
        "order_id": ORDER, "title": work["official_title"], "locale": "en-GB",
        "chapter_number": chapter, "part_number": part,
        "next_chapter": chapter, "next_part": part, "complete_length_only": False,
        "chapter_title": ch["chapter_title"],
        "section_plan": ch["four_mandatory_sections"],
        "practical_deliverable": ch["individually_assessed_professional_output"],
        "current_chapter_prose_words": counts[str(chapter)],
        "global_verified_draft_words": total,
        "next_segment_goal_words": 750,
        "previous_chapter_context_tail": last_context,
        "foundational_source_records": accessible,
        "stage3_relevant_research_claim_ids": sorted(citation_ids),
        "source_gaps_pending": ch["scientific_primary_sources_to_extend"],
        "safety_constraints": [
            "No medical or clinical procedure, pathogen culture, direct human feeding, or unsupported husbandry threshold.",
            "No species substitution: distinguish Hirudo medicinalis, H. verbana, H. orientalis.",
            "No fabricated data, DOI, regulatory permission, certification, or independent human review.",
            "All worked numeric examples are clearly labelled hypothetical assumptions.",
            "Explain professional veterinary, wildlife, water, safety and applicable jurisdiction checks."
        ],
        "output_rule": "Write only new substantive English textbook prose for this chapter; no outline-only answer and no padded repetition."
    }

def ensure_private():
    if PRIVATE.is_symlink():
        reject("UNSAFE_PRIVATE_SYMLINK")
    PRIVATE.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(PRIVATE, 0o700)

def save_once(path, data):
    if path.is_symlink() or path.exists():
        reject("IMMUTABLE_OUTPUT_COLLISION_" + path.name)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(str(path), flags, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())

def save_atomic(path, payload):
    fd, name = tempfile.mkstemp(prefix=".leech-status-", dir=str(PRIVATE))
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(name, 0o600)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)

def accept(chunks, body):
    work, chapters, sources = source_evidence()
    counts, total, chapter, part = state(chunks)
    if chapter is None:
        reject("MANUSCRIPT_ALREADY_LENGTH_COMPLETE")
    if len(body.encode("utf-8")) > 48000 or len(body.encode("utf-8")) < 1200:
        reject("SEGMENT_BYTES_OUT_OF_RANGE")
    if any(marker in body.casefold() for marker in
           ("lorem ipsum", "as an ai language model", "[insert ", "[citation needed]",
            "this is a placeholder", "## references", "bibliography\n")):
        reject("CONTENT_INTEGRITY_MARKER")
    current = words(body)
    if not 300 <= len(current) <= 1600 or len(set(current)) < 135:
        reject("SEGMENT_SUBSTANCE_OR_DIVERSITY_INVALID")
    shingles = [tuple(current[i:i + 12]) for i in range(0, len(current) - 11, 4)]
    if len(set(shingles)) / max(1, len(shingles)) < 0.91:
        reject("SEGMENT_REPETITIVE")
    if chunks[chapter]:
        prior = words("\n".join(text for _, text in chunks[chapter]))
        old_set = {tuple(prior[i:i + 12]) for i in range(0, len(prior) - 11, 3)}
        if sum(x in old_set for x in shingles) / max(1, len(shingles)) > 0.09:
            reject("SEGMENT_DUPLICATES_PREVIOUS")
    ensure_private()
    name = "chapter-%02d-part-%03d.md" % (chapter, part)
    data = (body.rstrip() + "\n").encode("utf-8")
    save_once(PRIVATE / name, data)
    chunks[chapter].append((part, body))
    counts, total, next_chapter, next_part = state(chunks)
    status = {
        "schema": "saeit.factory.leech-original-manuscript-progress.v1",
        "order_id": ORDER, "locale": "en-GB",
        "accepted_chunk": name, "accepted_chunk_sha256": hashlib.sha256(data).hexdigest(),
        "accepted_chunk_substantive_words": len(current),
        "total_substantive_draft_words": total, "per_chapter_words": counts,
        "next_chapter": next_chapter, "next_part": next_part,
        "target_words": REQUIRED_CHAPTERS * TARGET_PER_CHAPTER,
        "original_prose_independent_review": False, "quality1000_approved": False,
        "commercial_release": False, "public_distribution_allowed": False,
        "inference_backend": "offline Qwen/Qwen3-4B-GGUF Q4_K_M on free public GitHub runner",
        "model_license": "Apache-2.0",
        "model_source": "https://huggingface.co/Qwen/Qwen3-4B-GGUF",
        "model_is_not_independent_scientific_reviewer": True,
        "updated_utc": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }
    save_atomic(PRIVATE / "status.json", (json.dumps(status, sort_keys=True) + "\n").encode())
    assembled = False
    if next_chapter is None:
        if total < MIN_WORDS:
            reject("MANUSCRIPT_NOT_LONG_ENOUGH")
        book = "# " + work["official_title"] + "\n\n"
        for i in range(1, REQUIRED_CHAPTERS + 1):
            book += "\n\n## Chapter %d: %s\n\n" % (i, chapters[i - 1]["chapter_title"])
            book += "\n\n".join(text for _, text in chunks[i]) + "\n"
        save_once(PRIVATE / "complete-unreviewed.md", book.encode("utf-8"))
        assembled = True
    return {"schema": status["schema"], "order_id": ORDER, "original_prose_accepted": True,
            "accepted_words": len(current), "total_unreviewed_original_words": total,
            "chapter_completed": counts[str(chapter)] >= TARGET_PER_CHAPTER,
            "next_chapter": next_chapter, "next_part": next_part,
            "full_private_unreviewed_manuscript_assembled": assembled,
            "quality1000_approved": False, "commercial_release": False}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("prepare", "accept", "status"))
    args = parser.parse_args()
    work, chapters, sources = source_evidence()
    if args.mode == "prepare":
        result = make_prompt(work, chapters, sources, list_parts())
    elif args.mode == "status":
        _, total, chapter, part = state(list_parts())
        result = {"order_id": ORDER, "verified_unreviewed_prose_words": total,
                  "next_chapter": chapter, "next_part": part, "quality1000_approved": False}
    else:
        ensure_private()
        lock = PRIVATE / ".authoring.lock"
        if lock.is_symlink():
            reject("UNSAFE_LOCK")
        with lock.open("a+b") as f:
            os.fchmod(f.fileno(), 0o600)
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            raw = sys.stdin.buffer.read(48001)
            if len(raw) > 48000:
                reject("OVERSIZED_GENERATION")
            result = accept(list_parts(), raw.decode("utf-8"))
    print(json.dumps(result, sort_keys=True, ensure_ascii=False))

if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, RuntimeError, UnicodeError, KeyError, TypeError) as exc:
        print("LEECH_PRIVATE_WRITER_BLOCKED: " + str(exc)[:220], file=sys.stderr)
        raise SystemExit(2)
