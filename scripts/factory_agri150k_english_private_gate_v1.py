#!/usr/bin/env python3
"""Private, fail-closed 150,001+ English word contract for AGRI-001.

Does not change the existing 100k/200-title legacy program or authorize sales.
Only creates an immutable PRIVATE_QA plan inside the VPS factory when invoked.
"""
from __future__ import annotations
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

SCHEMA = "saeit.agri150k.english-private-plan.v1"
PRODUCT_ID = "AGRI-001"
TITLE = "Houseplant Rescue Guide"
MIN_WORDS = 150_001
TARGET_PER_CHAPTER = 5_300
MIN_PER_CHAPTER = 5_000
CHAPTER_TITLES = (
    "Diagnostic reasoning and evidence hierarchies",
    "Botanical anatomy for rescue decisions",
    "Plant physiology and stress signaling",
    "Taxonomy and identification uncertainty",
    "Root-system health and hydraulic function",
    "Substrate physics, aeration, and compaction",
    "Irrigation diagnostics and water balance",
    "Water quality, salinity, and conductivity",
    "Light spectra, photoperiod, and acclimation",
    "Temperature, humidity, and vapor pressure",
    "Nutrition, pH, and deficiency diagnosis",
    "Leaf symptom differential diagnosis",
    "Stem and crown failure diagnosis",
    "Root rot and pathogen differential diagnosis",
    "Arthropod pest identification",
    "Integrated pest management decisions",
    "Disease sanitation and biosecurity",
    "Transplanting and recovery interventions",
    "Propagation and conservation of specimens",
    "Species-specific decision boundaries",
    "Indoor environmental measurement systems",
    "Experimental design and causal inference",
    "Uncertainty, error propagation, and statistics",
    "Field records, images, and reproducibility",
    "Decision trees and intervention thresholds",
    "Occupational safety and chemical stewardship",
    "Service-business workflow and client consent",
    "Cost accounting and service economics",
    "Advanced rescue case studies and failures",
    "Capstone diagnosis, assessment, and ethics",
)
SOURCES = (
    {"id": "UMD-2025", "institution": "University of Maryland Extension",
     "title": "Diagnose Indoor Plant Problems",
     "url": "https://extension.umd.edu/resource/diagnose-indoor-plant-problems"},
    {"id": "UCIPM-2020", "institution": "University of California IPM",
     "title": "Houseplant Problems",
     "url": "https://ipm.ucanr.edu/home-and-landscape/houseplant-problems/"},
    {"id": "ISU-HOUSEPLANTS", "institution": "Iowa State University Extension",
     "title": "How to Care for Houseplants",
     "url": "https://yardandgarden.extension.iastate.edu/how-to/how-care-houseplants"},
)
WORD = re.compile(r"[^\W\d_][\w’'-]*", re.UNICODE)


def plan():
    assert len(CHAPTER_TITLES) == 30
    return {
        "schema": SCHEMA, "product_id": PRODUCT_ID, "title": TITLE,
        "language": "en-US", "storefront": "mojplaywin.com",
        "state": "PRIVATE_QA", "minimum_original_prose_words": MIN_WORDS,
        "target_original_prose_words": len(CHAPTER_TITLES) * TARGET_PER_CHAPTER,
        "chapters": [{"number": n, "title": title, "minimum_words": MIN_PER_CHAPTER,
                      "target_words": TARGET_PER_CHAPTER, "state": "AWAITING_AUTHORING"}
                     for n, title in enumerate(CHAPTER_TITLES, 1)],
        "starter_reference_leads_unverified_for_each_claim": list(SOURCES),
        "chapter_acceptance": [
            "original substantive prose", "worked numerical examples with assumptions",
            "reproducible diagnosis and safety stop conditions", "exercises and answers",
            "claim-to-source trace with fulltext verification", "limitations and uncertainty",
            "no invented field trials, references, endorsements, or licenses"],
        "requires_independent_scientific_review": True,
        "requires_independent_qc1000": True,
        "requires_rights_verification": True,
        "requires_verified_checkout_and_download": True,
        "publication_allowed": False, "discount_authority": "OWNER_ONLY",
    }


def prose_tokens(markdown):
    lines = []
    fenced = False
    references = False
    for raw in markdown.splitlines():
        s = raw.strip()
        if s.startswith(("~~~", "```")):
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


def audit(chapter_texts):
    if len(chapter_texts) != len(CHAPTER_TITLES) or not all(isinstance(x, str) for x in chapter_texts):
        raise ValueError("REQUIRE_30_ENGLISH_CHAPTERS")
    counts = [len(prose_tokens(x)) for x in chapter_texts]
    total = sum(counts)
    paragraphs = []
    for chapter in chapter_texts:
        for p in re.split(r"\n\s*\n", chapter):
            toks = prose_tokens(p)
            if len(toks) >= 35:
                paragraphs.append(" ".join(toks))
    duplicates = len(paragraphs) - len(set(paragraphs))
    tokens = [t for text in chapter_texts for t in prose_tokens(text)]
    shingles = [tuple(tokens[i:i + 12]) for i in range(0, max(len(tokens) - 11, 0), 6)]
    novelty = len(set(shingles)) / len(shingles) if shingles else 0.0
    findings = []
    if total < MIN_WORDS:
        findings.append("P0_UNDER_150001_ORIGINAL_WORDS")
    if any(n < MIN_PER_CHAPTER for n in counts):
        findings.append("P0_UNDERDEVELOPED_CHAPTER")
    if duplicates or novelty < .85:
        findings.append("P0_REPETITION_OR_PADDING")
    return {"schema": SCHEMA, "product_id": PRODUCT_ID,
            "original_prose_words_unreviewed": total,
            "chapter_words": counts, "duplicate_long_paragraphs": duplicates,
            "sampled_shingle_novelty": round(novelty, 5),
            "mechanical_findings": findings,
            "mechanically_eligible_for_independent_review": not findings,
            "independent_scientific_approval": False, "qc1000_approved": False,
            "publication_allowed": False}


def install_private(factory_root):
    base = Path(factory_root).resolve() / "production-instructions"
    if not base.is_dir() or base.is_symlink():
        raise ValueError("PRIVATE_FACTORY_AREA_NOT_ACCESSIBLE")
    stage = base / "stage-05"
    # A symlink at an intermediate directory bypasses dest.is_symlink().
    # Refuse it before any mkdir/write, including if it points outside the factory.
    if stage.is_symlink():
        raise ValueError("UNSAFE_PRIVATE_DIRECTORY")
    stage.mkdir(parents=True, exist_ok=True, mode=0o700)
    if stage.is_symlink() or stage.resolve() != base / "stage-05":
        raise ValueError("UNSAFE_PRIVATE_DIRECTORY")
    dest = stage / "doctoral-monographs-150k-en-v1"
    if dest.is_symlink():
        raise ValueError("UNSAFE_PRIVATE_DIRECTORY")
    dest.mkdir(exist_ok=True, mode=0o700)
    if dest.is_symlink() or dest.resolve() != stage / "doctoral-monographs-150k-en-v1":
        raise ValueError("UNSAFE_PRIVATE_DIRECTORY")
    lock = dest / ".agri150k-plan.lock"
    if lock.is_symlink():
        raise ValueError("UNSAFE_PRIVATE_LOCK")
    with lock.open("a+b") as fd:
        os.fchmod(fd.fileno(), 0o600)
        fcntl.flock(fd.fileno(), fcntl.LOCK_EX)
        payload = (json.dumps(plan(), ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()
        path = dest / (PRODUCT_ID + ".json")
        if path.is_symlink():
            raise ValueError("UNSAFE_PRIVATE_PLAN")
        if path.exists():
            if path.read_bytes() != payload:
                raise ValueError("IMMUTABLE_PLAN_CONFLICT")
            return {"state": "EXISTING_IDENTICAL_PRIVATE_PLAN", "sha256": hashlib.sha256(payload).hexdigest()}
        tmp_fd, tmp = tempfile.mkstemp(prefix=".agri150k-", dir=dest)
        try:
            with os.fdopen(tmp_fd, "wb") as out:
                os.fchmod(out.fileno(), 0o600)
                out.write(payload)
                out.flush()
                os.fsync(out.fileno())
            os.replace(tmp, path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
        return {"state": "NEW_PRIVATE_PLAN", "sha256": hashlib.sha256(payload).hexdigest()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--factory-private", type=Path)
    parser.add_argument("--show-plan", action="store_true")
    args = parser.parse_args()
    if args.show_plan:
        print(json.dumps(plan(), ensure_ascii=False, indent=2))
    elif args.factory_private:
        print(json.dumps(install_private(args.factory_private)))
    else:
        parser.error("provide --show-plan or --factory-private")


if __name__ == "__main__":
    main()
