#!/usr/bin/env python3
"""Private, original 100,000-word doctoral monograph production contract.

Produces actual *chapter authoring work orders*, not padded manuscripts or
fabricated science. Screens existing Stage5 v003 bytes in the seller's language.
Every manuscript remains private pending real fulltext verification, originality
assessment, independent QC1000 and end-to-end buyer checkout/delivery proof.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import zipfile

SCHEMA = "saeit.agri200.doctoral-monograph100k.v1"
CATALOG_ID = re.compile(r"AGRI-(\d{3})\Z")
ORDER = re.compile(r"WO-\d{8}\Z")
HEX = re.compile(r"[0-9a-f]{64}\Z")
WORD = re.compile(r"[^\W\d_][\w\u200c’'-]*", re.UNICODE)
CHAPTER_COUNT = 20
MIN_SALE_EDITION_PROSE_WORDS = 100_000
CHAPTER_TARGET_WORDS = 5_250
CHAPTER_MIN_WORDS = 4_000
MAX_SOURCE_ZIP = 16_000_000
FACETS = (
    "disciplinary scope and clearly defined customer problem",
    "international and local context with applicability limits",
    "history of methods and development of the evidence base",
    "systematic source-selection and evidence-quality methods",
    "fundamental mechanisms and competing explanations",
    "measurement units, metrics and calibration",
    "baseline assessment with reproducible records",
    "diagnosis and classification of real-world situations",
    "design of a defensible intervention or workflow",
    "stepwise practical execution with stop conditions",
    "quantitative analysis, calculations and uncertainty",
    "worked case study A with explicit source provenance",
    "worked case study B with comparative limitations",
    "common failures, troubleshooting and root-cause analysis",
    "local adaptation, accessibility and feasibility",
    "environmental impacts, safety, legal and ethical boundaries",
    "cost modeling, resources and economic decision support",
    "data collection, validation and reproducibility",
    "advanced applications, open disputes and research gaps",
    "integrated applied project, assessment and future work",
)
assert len(FACETS) == CHAPTER_COUNT


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def safe_json(path: Path, maximum: int = 250_000) -> dict:
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= maximum:
        raise ValueError("UNSAFE_PRIVATE_JSON")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("NOT_A_JSON_OBJECT")
    return data


def canonical(data: dict) -> bytes:
    return (json.dumps(data, ensure_ascii=False, sort_keys=True,
                       indent=2) + "\n").encode("utf-8")


def catalog_rows(path: Path) -> tuple[list[tuple[str, str, str]], str]:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 70_000:
        raise ValueError("CATALOG_UNSAFE")
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        parts = [value.strip() for value in line.split("|")]
        if len(parts) != 3 or not CATALOG_ID.fullmatch(parts[0]):
            raise ValueError("INVALID_CATALOG_ITEM")
        rows.append(tuple(parts))
    if ([r[0] for r in rows] != [f"AGRI-{i:03d}" for i in range(1, 201)]
            or len({r[1] for r in rows}) != 200
            or len({r[2].casefold() for r in rows}) != 200):
        raise ValueError("NOT_200_DISTINCT_TOPICS")
    return rows, digest(path.read_bytes())


def prose_tokens(markdown: str) -> list[str]:
    """Count original instructional prose, not headings, citations or padding."""
    lines = []
    fenced = False
    reference_section = False
    for raw in markdown.splitlines():
        line = raw.strip()
        if line.startswith("~~~") or line.startswith("'''") or line.startswith("&#96;&#96;&#96;") or line.startswith(chr(96) * 3):
            fenced = not fenced
            continue
        if fenced or not line or line.startswith(("#", ">", "|", "---")):
            if line.startswith("## "):
                reference_section = bool(re.search(
                    r"(?:references|bibliography|منابع|کتابنامه)", line, re.I))
            continue
        if reference_section:
            continue
        # Exclude lists of sources and bare links from counted prose.
        if line.startswith(("- http", "* http", "http://", "https://")):
            continue
        line = re.sub(r"https?://\S+", " ", line)
        line = re.sub(r"\[[^\]]{1,200}\]\([^)]{1,800}\)", " ", line)
        line = re.sub(r"\[REF:[^\]]+\]", " ", line)
        lines.append(line)
    return [w.casefold() for w in WORD.findall(" ".join(lines)) if any(c.isalpha() for c in w)]


def original_prose_metrics(chapters: list[str]) -> dict:
    if len(chapters) != CHAPTER_COUNT:
        raise ValueError("DOCTORAL_CHAPTER_COUNT_INVALID")
    counts = []
    all_tokens = []
    paragraphs = []
    for chapter in chapters:
        if not isinstance(chapter, str) or len(chapter.encode("utf-8")) > 2_000_000:
            raise ValueError("CHAPTER_UNSAFE")
        tokens = prose_tokens(chapter)
        counts.append(len(tokens))
        all_tokens.extend(tokens)
        for paragraph in re.split(r"\n\s*\n", chapter):
            ps = prose_tokens(paragraph)
            if len(ps) >= 35:
                paragraphs.append(" ".join(ps))
    repeats = len(paragraphs) - len(set(paragraphs))
    repeated_fraction = repeats / len(paragraphs) if paragraphs else 1.0
    # Sample overlapping 12-word shingles: repeated scaffolds cannot fill a book.
    shingles = [tuple(all_tokens[i:i + 12])
                for i in range(0, max(len(all_tokens) - 11, 0), 6)]
    novelty = len(set(shingles)) / len(shingles) if shingles else 0.0
    lexical_diversity = len(set(all_tokens)) / len(all_tokens) if all_tokens else 0.0
    total = sum(counts)
    reasons = []
    if total < MIN_SALE_EDITION_PROSE_WORDS:
        reasons.append("P0_ORIGINAL_PROSE_UNDER_100000_WORDS")
    if any(n < CHAPTER_MIN_WORDS for n in counts):
        reasons.append("P0_UNDERDEVELOPED_CHAPTERS")
    if repeated_fraction > 0.05 or novelty < 0.85 or lexical_diversity < 0.015:
        reasons.append("P0_REPETITIVE_PADDING_OR_LOW_NOVELTY")
    return {
        "substantive_prose_words": total,
        "minimum_required_words": MIN_SALE_EDITION_PROSE_WORDS,
        "chapter_words": counts,
        "weak_chapters": [i + 1 for i, n in enumerate(counts) if n < CHAPTER_MIN_WORDS],
        "paragraph_duplicate_fraction": round(repeated_fraction, 5),
        "shingle_novelty": round(novelty, 5),
        "lexical_diversity": round(lexical_diversity, 5),
        "meets_mechanical_length_and_novelty": not reasons,
        "critical_findings": reasons,
        "independent_doctoral_science_review_verified": False,
        "qc1000_approved": False,
        "commercial_release": False,
    }


def verify_order(area: Path, ident: str, fa: str, en: str,
                 rank: int, order_id: str) -> None:
    order = safe_json(area / "orders" / (order_id + ".json"))
    identity = {"id": ident, "fa": fa, "en": en}
    expected = digest(json.dumps(identity, ensure_ascii=False, sort_keys=True,
                                 separators=(",", ":")).encode("utf-8"))
    if (order.get("id") != order_id or order.get("source_product_id") != ident
            or order.get("priority_rank") != rank or order.get("source_sha256") != expected):
        raise ValueError("CATALOG_ORDER_IDENTITY_MISMATCH:" + ident)


def book_plan(ident: str, fa: str, en: str, rank: int,
              order_id: str, catalog_sha: str) -> dict:
    english = rank <= 100
    locale, title, site, currency = (
        ("en-US", en, "mojplaywin.com", "USD") if english else
        ("fa-IR", fa, "zomorodmelal.ir", "IRR"))
    return {
        "schema": SCHEMA, "id": ident, "rank": rank, "order_id": order_id,
        "catalog_sha256": catalog_sha, "selling_locale": locale,
        "selling_title": title, "storefront": site, "currency": currency,
        "minimum_original_prose_words": MIN_SALE_EDITION_PROSE_WORDS,
        "authoring_target_original_prose_words": CHAPTER_COUNT * CHAPTER_TARGET_WORDS,
        "chapters_required": CHAPTER_COUNT,
        "chapter_work_units": [
            {"number": i + 1, "subject": title, "focus": facet,
             "minimum_original_prose_words": CHAPTER_MIN_WORDS,
             "target_original_prose_words": CHAPTER_TARGET_WORDS,
             "status": "AWAITING_ORIGINAL_AUTHORING_AND_SOURCES",
             "requires_fulltext_and_claim_to_page_provenance": True,
             "requires_real_domain_examples_and_reproducible_methods": True}
            for i, facet in enumerate(FACETS)
        ],
        "primary_research_license_and_retraction_review_required": True,
        "standalone_originality_verification_required": True,
        "specialist_and_independent_QC1000_required": True,
        "real_buyer_checkout_and_delivery_test_required": True,
        "discount_authority": "OWNER_ONLY",
        "discount_percent": 0,
        "generated_chapter_count": 0,
        "quality1000_approved": False,
        "sales_enabled": False,
        "public_listing_enabled": False,
        "state": "PRIVATE_DOCTORAL_AUTHORING_BACKLOG",
    }


def inspect_v003(area: Path, ident: str, order_id: str, locale: str) -> dict:
    name = order_id + "--r001.json"
    source = area / "stage-05/source-grounded-v003-manifests" / name
    if not source.is_file() or source.is_symlink():
        return {"status": "SOURCE_DRAFT_NOT_AVAILABLE", "existing_prose_words": 0}
    try:
        info = safe_json(source)
        relative = info.get("archive_relative_path")
        if (info.get("order_id") != order_id
                or info.get("commercial_release") is not False
                or not isinstance(relative, str)):
            raise ValueError("V003_DRAFT_IDENTITY_INVALID")
        part = Path(relative)
        if (part.is_absolute() or ".." in part.parts or len(part.parts) != 4 or
                tuple(part.parts[:2]) != ("stage-05", "source-grounded-v003") or
                part.parts[2] != order_id + "--r001" or
                not part.name.endswith(".zip")):
            raise ValueError("V003_ARCHIVE_PATH_UNSAFE")
        path = area
        for segment in part.parts:
            path = path / segment
            if path.is_symlink():
                raise ValueError("V003_ARCHIVE_SYMLINK")
        if not path.is_file() or not 0 < path.stat().st_size <= MAX_SOURCE_ZIP:
            raise ValueError("V003_ARCHIVE_MISSING_OR_LARGE")
        raw = path.read_bytes()
        if digest(raw) != info.get("zip_sha256") or len(raw) != info.get("zip_bytes"):
            raise ValueError("V003_ARCHIVE_HASH_MISMATCH")
        with zipfile.ZipFile(path) as archive:
            if archive.testzip() is not None:
                raise ValueError("V003_ARCHIVE_CRC_FAILURE")
            target = "agri-" + order_id + "--r001-v003/" + locale + ".md"
            member = archive.getinfo(target)
            if member.file_size > 2_000_000:
                raise ValueError("V003_MANUSCRIPT_TOO_LARGE")
            text = archive.read(target).decode("utf-8")
        count = len(prose_tokens(text))
        return {"status": "VERIFIED_PRIOR_RESEARCH_COMPANION",
                "existing_prose_words": count,
                "words_still_required": max(0, MIN_SALE_EDITION_PROSE_WORDS - count),
                "draft_qualified_for_sale": False}
    except (ValueError, OSError, KeyError, UnicodeError, zipfile.BadZipFile) as exc:
        return {"status": "INVALID_PRIVATE_DRAFT", "existing_prose_words": 0,
                "reason": type(exc).__name__ + ":" + str(exc)[:90]}


def private_dir(path: Path) -> None:
    if path.is_symlink():
        raise ValueError("UNSAFE_DESTINATION_LINK")
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not path.is_dir() or path.is_symlink():
        raise ValueError("UNSAFE_PRIVATE_DIRECTORY")


def write_once(path: Path, data: dict) -> bool:
    raw = canonical(data)
    if path.is_symlink():
        raise ValueError("UNSAFE_TARGET_LINK")
    if path.exists():
        if not path.is_file() or path.read_bytes() != raw:
            raise ValueError("DOCTORAL_WORK_ORDER_IMMUTABLE_CONFLICT:" + path.name)
        return False
    private_dir(path.parent)
    handle, temporary = tempfile.mkstemp(prefix=".doctoral100k-", dir=str(path.parent))
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return True


def execute(factory_private: Path, catalog: Path) -> dict:
    rows, sha = catalog_rows(catalog)
    area = factory_private / "production-instructions"
    if area.is_symlink() or not area.is_dir():
        raise ValueError("FACTORY_AREA_INVALID")
    index = safe_json(area / "owner-agri200-p0-index.json")
    ids = index.get("order_ids_ranked")
    if (index.get("catalog_sha256") != sha or index.get("topic_count") != 200
            or index.get("edition_goal_count") != 400 or
            not isinstance(ids, list) or len(ids) != 200
            or len(set(ids)) != 200 or
            any(not isinstance(item, str) or not ORDER.fullmatch(item) for item in ids)):
        raise ValueError("P0_INDEX_NOT_THE_ACTUAL_200")
    private = area / "stage-05/doctoral-monographs-100k-v1"
    private_dir(private)
    private_dir(private / "plans")
    private_dir(private / "prior-draft-screen")
    lock = private / ".book-plans.lock"
    if lock.is_symlink():
        raise ValueError("UNSAFE_PLAN_LOCK")
    with lock.open("a+b") as handle:
        os.fchmod(handle.fileno(), 0o600)
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        counts = Counter()
        raw_counts = []
        for rank, ((ident, fa, en), work_id) in enumerate(zip(rows, ids), 1):
            verify_order(area, ident, fa, en, rank, work_id)
            plan = book_plan(ident, fa, en, rank, work_id, sha)
            counts["new_plans"] += int(write_once(private / "plans" / (ident + ".json"), plan))
            old = inspect_v003(area, ident, work_id, plan["selling_locale"])
            # Screens are bound to the old source ZIP and never grant approval.
            old_packet = {"schema": SCHEMA, "id": ident, "order_id": work_id,
                          "selling_locale": plan["selling_locale"],
                          "prior_private_draft": old,
                          "new_minimum_original_prose_words": MIN_SALE_EDITION_PROSE_WORDS,
                          "accepted_original_prose_words": 0,
                          "source_draft_is_not_a_completed_monograph": True,
                          "independent_qc1000_approved": False,
                          "commercial_release": False}
            counts["new_screens"] += int(write_once(
                private / "prior-draft-screen" / (ident + ".json"), old_packet))
            counts[old["status"]] += 1
            raw_counts.append(old["existing_prose_words"])
        report = {
            "schema": SCHEMA, "catalog_sha256": sha,
            "customer_product_count": 200,
            "english_usd_targets": 100, "persian_irr_targets": 100,
            "minimum_original_words_per_selling_edition": MIN_SALE_EDITION_PROSE_WORDS,
            "minimum_sale_language_corpus_words": 20_000_000,
            "chapter_authoring_work_units": 200 * CHAPTER_COUNT,
            "new_private_plans": counts["new_plans"],
            "new_private_source_screens": counts["new_screens"],
            "verified_old_research_companions": counts["VERIFIED_PRIOR_RESEARCH_COMPANION"],
            "missing_or_unverified_previous_drafts":
                200 - counts["VERIFIED_PRIOR_RESEARCH_COMPANION"],
            "largest_existing_research_companion_prose_words": max(raw_counts, default=0),
            "full_100k_word_monographs_completed": 0,
            "independently_approved": 0, "published_for_sale": 0,
            "discounts_created": 0,
            "sites_modified": False,
            "next_required_work": "AUTHOR_20_ORIGINAL_SOURCE_VERIFIED_CHAPTERS_PER_PRODUCT_AND_RUN_REAL_QC",
        }
        # Stable status, not a fake content completion counter.
        baseline = dict(report)
        baseline.pop("new_private_plans")
        baseline.pop("new_private_source_screens")
        write_once(private / "generation-baseline-20261024.json", baseline)
        return report


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--catalog", type=Path)
    p.add_argument("--factory-private", type=Path)
    p.add_argument("--selftest", action="store_true")
    a = p.parse_args()
    if a.selftest:
        assert len(FACETS) == CHAPTER_COUNT
        assert len(prose_tokens("## Test\n\nOne two سه چهار و پنج.")) == 6
        short = original_prose_metrics(["Unique short topic detail " + str(i)
                                         for i in range(CHAPTER_COUNT)])
        assert "P0_ORIGINAL_PROSE_UNDER_100000_WORDS" in short["critical_findings"]
        assert book_plan("AGRI-001", "نمونه آزمایشی", "A Test Plan", 1,
                         "WO-00000001", "a" * 64)["selling_locale"] == "en-US"
        assert book_plan("AGRI-101", "موضوع آزمایشی", "An Example", 101,
                         "WO-00000101", "a" * 64)["selling_locale"] == "fa-IR"
        print("AGRI200_DOCTORAL100K_CONTRACT_SELFTEST=PASS")
        return
    if not a.catalog or not a.factory_private:
        p.error("--catalog and --factory-private required")
    try:
        result = execute(a.factory_private, a.catalog)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print("AGRI200_DOCTORAL100K_BLOCKED:" + type(exc).__name__ +
              ":" + str(exc)[:160], file=sys.stderr)
        raise SystemExit(1) from exc
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
