#!/usr/bin/env python3
"""Private, zero-paid-API, fail-closed assembly and release preflight for WO-26102501.

This does NOT approve research claims, editorial quality, QC1000, clinical
guidance, checkout, invoices, publication or public distribution.
"""
from __future__ import annotations
import argparse
import fcntl
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys

WRITER = Path("/home/githubops/factory-runtime/operations/production-instructions/leech-professional-author.py")
MINIMUM_CHAPTER_WORDS = 5300
CHAPTERS = 30
MINIMUM_BOOK_WORDS = 159000
DOMAIN = ("farm", "facility", "breeding", "operator", "water", "stock", "biosecurity", "cocoon", "enclosure")
PLACEHOLDERS = ("lorem ipsum", "[citation needed]", "[insert ", "placeholder text", "as an ai language model")

def load_writer(path=WRITER):
    if path.is_symlink() or not path.is_file() or not (1000 <= path.stat().st_size <= 100000):
        raise RuntimeError("PRIVATE_LEECH_WRITER_MISSING_OR_UNSAFE")
    spec = importlib.util.spec_from_file_location("private_leech_original_writer", str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if module.ORDER != "WO-26102501" or module.REQUIRED_CHAPTERS != CHAPTERS:
        raise RuntimeError("LEECH_ORDER_OR_CHAPTER_CONTRACT_CHANGED")
    return module

def render_book(writer, manifest, chapters):
    pieces = ["# " + manifest["official_title"] + "\n\n"]
    for number in range(1, CHAPTERS + 1):
        pieces.append("\n\n## Chapter %d: %s\n\n" %
                      (number, chapters[number - 1]["chapter_title"]))
        pieces.append("\n\n".join(text for _, text in manifest["_chunks"][number]) + "\n")
    return "".join(pieces).encode("utf-8")

def content_checks(writer, chunks, counts):
    repeated = 0
    total_shingles = 0
    seen = set()
    failures = []
    for number in range(1, CHAPTERS + 1):
        text = "\n\n".join(t for _, t in chunks[number])
        words = writer.words(text)
        if counts[str(number)] != len(words) or len(words) < MINIMUM_CHAPTER_WORDS:
            failures.append("CHAPTER_WORDS_" + str(number))
        if not any(term in text.lower() for term in DOMAIN):
            failures.append("FARM_PRACTICE_NOT_VISIBLE_" + str(number))
        if any(token in text.casefold() for token in PLACEHOLDERS):
            failures.append("PLACEHOLDER_" + str(number))
        if sum(1 for line in text.splitlines() if line.strip().startswith("#")) < 3:
            failures.append("CHAPTER_SUBSECTIONS_" + str(number))
        for i in range(0, len(words) - 15, 7):
            phrase = tuple(words[i:i + 16])
            if phrase in seen:
                repeated += 1
            seen.add(phrase)
            total_shingles += 1
    # This is merely a lexical gate: semantic redundancy still needs review.
    if repeated / max(1, total_shingles) > 0.025:
        failures.append("CROSS_CHAPTER_EXACT_REPETITION")
    return failures, {"matching_16word_shingles": repeated,
                      "sampled_16word_shingles": total_shingles}

def verify(mode="inspect", writer=None):
    w = writer or load_writer()
    work, chapters, sources = w.source_evidence()
    if not (len(sources) >= 7 and len(chapters) == CHAPTERS):
        raise RuntimeError("SOURCE_OR_CHAPTER_PROVENANCE_FAILED")
    if w.PRIVATE.is_symlink() or (w.PRIVATE.exists() and not w.PRIVATE.is_dir()):
        raise RuntimeError("UNSAFE_PRIVATE_BOOK_LOCATION")
    if not w.PRIVATE.exists():
        return {"order_id":w.ORDER, "state":"not_started",
                "review_passed":False, "quality1000_approved":False,
                "publication_authorized":False, "paid_api_cost_usd":0}
    lock = w.PRIVATE / ".authoring.lock"
    if lock.is_symlink():
        raise RuntimeError("UNSAFE_AUTHORING_LOCK")
    with lock.open("a+b") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        chunks = w.list_parts()
        counts, total, next_chapter, next_part = w.state(chunks)
        if next_chapter is not None:
            return {"order_id":w.ORDER, "state":"authoring_in_progress",
                    "words":total, "required_words":MINIMUM_BOOK_WORDS,
                    "next_chapter":next_chapter, "next_part":next_part,
                    "review_passed":False, "quality1000_approved":False,
                    "publication_authorized":False, "paid_api_cost_usd":0}
        if total < MINIMUM_BOOK_WORDS or any(x < MINIMUM_CHAPTER_WORDS for x in counts.values()):
            raise RuntimeError("BOOK_LENGTH_OR_CHAPTER_DISTRIBUTION_INVALID")
        status = w.safe_json(w.PRIVATE / "status.json")
        if (status.get("order_id") != w.ORDER
            or status.get("total_substantive_draft_words") != total
            or status.get("per_chapter_words") != counts
            or status.get("quality1000_approved") is not False
            or status.get("commercial_release") is not False
            or status.get("public_distribution_allowed") is not False):
            raise RuntimeError("PRIVATE_AUTHORING_RECEIPT_OR_RELEASE_GATE_INVALID")
        issues, repetitions = content_checks(w, chunks, counts)
        book = w.PRIVATE / "complete-unreviewed.md"
        expected = render_book(w, {**work, "_chunks":chunks}, chapters)
        repaired = False
        if book.is_symlink():
            raise RuntimeError("UNSAFE_ASSEMBLED_BOOK_LINK")
        if not book.exists():
            if mode == "finalize":
                w.save_once(book, expected)
                repaired = True
            else:
                issues.append("ASSEMBLED_MANUSCRIPT_MISSING")
        if book.exists() and (not book.is_file() or book.read_bytes() != expected):
            issues.append("ASSEMBLED_MANUSCRIPT_MISMATCH")
        result = {
            "order_id": w.ORDER, "state": "ready_for_independent_scientific_editorial_review"
              if not issues else "technical_prepublication_rework_required",
            "words": total, "chapters":CHAPTERS,
            "technical_integrity_passed": not issues, "issues": issues,
            "shingle_audit": repetitions, "assembled_book_regenerated_safely": repaired,
            "verified_book_sha256": hashlib.sha256(expected).hexdigest()
              if not issues else None,
            "scientific_references_independently_verified": False,
            "scientific_content_approved": False, "quality1000_approved":False,
            "publication_authorized":False, "paid_api_cost_usd":0
        }
        if mode == "finalize":
            # Recording a technical review signal is not a publishing approval.
            w.save_atomic(w.PRIVATE / "technical-prepublication-review.json",
                          (json.dumps(result,sort_keys=True)+"\n").encode("utf-8"))
        return result

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--mode",choices=("inspect","finalize"),default="inspect")
    args=parser.parse_args()
    print(json.dumps(verify(args.mode),sort_keys=True))

if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, RuntimeError, KeyError, TypeError) as exc:
        print("LEECH_PREPUBLICATION_FAIL_CLOSED: "+str(exc)[:180],file=sys.stderr)
        raise SystemExit(2)
