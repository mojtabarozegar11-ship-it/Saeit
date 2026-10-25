#!/usr/bin/env python3
"""Stage 6 private technical preflight and actionable revision queue.

Evidence integrity and mechanical checks are automatic; human scientific review
is NOT. No expert signatures, safety certifications, QA1000, public publishing,
or stage-7 clearance can be synthesized by this worker. Python stdlib only.
"""
import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys

REPORT = "saeit.factory.stage6.technical-preflight.v1"
REWORK = "saeit.factory.stage5.substantive-rework-request.v1"
LOCALES = ("fa-IR", "en-US")
MIN_WORDS = 1000
MAX_BYTES = 400000


def dependency(path, name):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise RuntimeError("STAGE6_DEPENDENCY_NOT_REGULAR")
    spec = importlib.util.spec_from_file_location(name, str(path))
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


def checked_read(root, name, loc, expected_sha):
    expected = root / name[:-5] / (loc + ".md")
    for ancestor in (root, root / name[:-5], expected):
        if ancestor.is_symlink():
            raise RuntimeError("STAGE6_UNSAFE_SYMLINK")
    if not expected.is_file() or not isinstance(expected_sha, str):
        raise RuntimeError("STAGE6_MISSING_MANUSCRIPT")
    size = expected.stat().st_size
    if not 0 < size <= MAX_BYTES:
        raise RuntimeError("STAGE6_INVALID_MANUSCRIPT_SIZE")
    body = expected.read_bytes()
    if hashlib.sha256(body).hexdigest() != expected_sha:
        raise RuntimeError("STAGE6_MANUSCRIPT_SHA_MISMATCH")
    text = body.decode("utf-8")
    if len(text.split()) < MIN_WORDS:
        raise RuntimeError("STAGE6_DRAFT_TOO_SHORT")
    return text


def preflight(area, name, lib, stage5):
    if lib.NAME.fullmatch(name) is None:
        raise RuntimeError("STAGE6_BAD_ORDER_FILENAME")
    handoff, prototype, design, research, order, editions = stage5.verified_stage4(area, name, lib)
    manifest = lib.read(area / "stage-05" / "completed-drafts" / name)
    original = lib.read(area / "stage-06" / "inbox" / name)
    receipt = lib.read(area / "stage-05" / "receipts" / name)
    for item in (manifest, original):
        lib.deny_approval(item)
    if (manifest.get("schema") != stage5.SCHEMA
            or manifest.get("stage") != 5
            or manifest.get("order_id") != handoff["order_id"]
            or manifest.get("revision") != handoff["revision"]
            or manifest.get("stage4_prototype_sha256") != lib.digest(prototype)
            or manifest.get("stage3_design_sha256") != lib.digest(design)
            or manifest.get("stage2_research_sha256") != lib.digest(research)
            or manifest.get("draft_files_created") is not True
            or manifest.get("independent_scientific_review") is not False
            or manifest.get("domain_accuracy_certified") is not False
            or manifest.get("real_world_field_testing") is not False
            or original.get("schema") != stage5.REVIEW
            or original.get("stage") != 6
            or original.get("order_id") != handoff["order_id"]
            or original.get("revision") != handoff["revision"]
            or original.get("stage5_manifest_sha256") != lib.digest(manifest)
            or original.get("stage4_prototype_sha256") != lib.digest(prototype)
            or original.get("human_review_completed") is not False
            or original.get("reviewer_signature_created") is not False
            or original.get("status") != "pending_independent_qualified_reviewer"
            or receipt.get("schema") != stage5.SCHEMA
            or receipt.get("stage_5_working_draft_created") is not True
            or receipt.get("stage5_manifest_sha256") != lib.digest(manifest)
            or receipt.get("stage6_review_packet_sha256") != lib.digest(original)
            or receipt.get("human_review_completed") is not False
            or receipt.get("quality1000_approved") is not False):
        raise RuntimeError("STAGE6_EVIDENCE_CHAIN_MISMATCH")
    claim_map = {c["id"]: c for c in research["claims"]}
    source_map = {s["id"]: s for s in research["sources"]}
    chapters = design.get("chapters", [])
    if not isinstance(chapters, list) or len(chapters) < 5:
        raise RuntimeError("STAGE6_CHAPTERS_MISSING")
    citations = set()
    for chapter in chapters:
        claim = claim_map.get(chapter.get("source_claim_id"))
        if not claim or set(chapter.get("source_ids", [])) != set(claim["source_ids"]):
            raise RuntimeError("STAGE6_CLAIM_CHAIN_INVALID")
        if not set(claim["source_ids"]).issubset(source_map):
            raise RuntimeError("STAGE6_SOURCE_CHAIN_INVALID")
        citations.update(claim["source_ids"])
    files = manifest.get("manuscript_files")
    hashes = manifest.get("manuscript_sha256")
    if (not isinstance(files, dict) or not isinstance(hashes, dict)
            or set(files) != set(LOCALES) or set(hashes) != set(LOCALES)
            or manifest.get("chapter_count") != len(chapters)):
        raise RuntimeError("STAGE6_MANUSCRIPT_MANIFEST_INVALID")
    editions_stats = {}
    for locale in LOCALES:
        if files[locale] != name[:-5] + "/" + locale + ".md":
            raise RuntimeError("STAGE6_UNSAFE_MANUSCRIPT_PATH")
        body = checked_read(area / "stage-05" / "drafts", name, locale, hashes[locale])
        count = sum(x.startswith("## فصل ") if locale == "fa-IR"
                    else x.startswith("## Chapter ") for x in body.splitlines())
        if count != len(chapters):
            raise RuntimeError("STAGE6_MANUSCRIPT_CHAPTER_COUNT")
        for src in citations:
            if src not in body:
                raise RuntimeError("STAGE6_MANUSCRIPT_MISSING_SOURCE_CITATION:" + str(src)[:100])
        if editions[locale]["title"] not in body:
            raise RuntimeError("STAGE6_LOCALE_TITLE_MISMATCH")
        editions_stats[locale] = {
            "sha256": hashes[locale], "word_count": len(body.split()),
            "chapters": count, "referenced_source_count": len(citations)}
    problems = []
    if manifest.get("draft_kind") == "original_bilingual_evidence_method_workbook":
        problems.append("METHOD_ONLY_DRAFT_NOT_SUBJECT_SPECIFIC_COMPLETED_MANUAL")
    else:
        problems.append("DOMAIN_COMPLETENESS_NOT_INDEPENDENTLY_VERIFIED")
    problems.extend([
        "FULL_TEXT_SOURCE_AND_METADATA_NOT_INDEPENDENTLY_VERIFIED",
        "DOMAIN_SPECIFIC_ACCURACY_AND_LOCAL_REGULATION_NOT_REVIEWED",
        "PRACTICAL_TEST_AND_BILINGUAL_EXPERT_REVIEW_MISSING",
    ])
    dossier = {
        "schema": REPORT, "stage": 6,
        "order_id": handoff["order_id"], "revision": handoff["revision"],
        "stage5_manifest_sha256": lib.digest(manifest),
        "stage6_request_sha256": lib.digest(original),
        "stage2_research_sha256": lib.digest(research),
        "integrity_preflight_passed": True,
        "technical_preflight_completed": True,
        "independent_scientific_review_passed": False,
        "stage6_completed": False, "stage7_authorized": False,
        "quality1000_approved": False, "commercial_release": False,
        "public_distribution_allowed": False,
        "content_readiness": "requires_stage5_substantive_revision_and_independent_review",
        "blocking_findings": problems,
        "bilingual_draft_measures": editions_stats,
        "source_audit_queue": [
            {"id": s["id"], "publisher": s["publisher"],
             "title": s["title"], "url": s["url"],
             "full_text_confirmed_by_independent_reviewer": False}
            for s in research["sources"]
        ],
        "claim_audit_queue": [
            {"claim_id": c["id"], "statement": c["statement"],
             "source_ids": c["source_ids"], "independently_validated": False}
            for c in research["claims"]
        ],
        "reviewer_checklist": original["review_required"],
        "no_automatic_human_attestation": True,
    }
    rework = {
        "schema": REWORK, "stage": 5, "order_id": handoff["order_id"],
        "revision_under_review": handoff["revision"],
        "stage6_preflight_sha256": lib.digest(dossier),
        "status": "awaiting_substantive_reauthoring",
        "fixes": [
            "Write genuinely topic-specific, source-grounded Persian and English chapters, not reusable methods-only boilerplate.",
            "Cross-check every factual claim against full original scientific publication, reporting units and uncertainty.",
            "Provide distinct domain-specific cases, non-fabricated examples and correct assessment answer keys.",
            "Resolve Iran and international applicability, safety caveats, and any legally regulated claims.",
            "Submit a NEW numbered order revision with linked sources and immutable new manuscript hashes for further review."
        ],
        "original_draft_preserved": True,
        "independent_reviewer_signature_created": False,
        "quality1000_approved": False,
        "public_distribution_allowed": False,
        "commercial_release": False
    }
    created = lib.once(area / "stage-06" / "technical-preflight" / name, dossier)
    lib.once(area / "stage-05" / "substantive-rework-inbox" / name, rework)
    return created


def fair_batch(area, names, batch, lib):
    """Cycle through all orders, including after a blocked or already-reviewed prefix."""
    cursor_path = area / "stage-06" / "round-robin-cursor.json"
    if cursor_path.is_symlink():
        raise RuntimeError("STAGE6_CURSOR_SYMLINK")
    state = lib.read(cursor_path) if cursor_path.exists() else {
        "schema": "saeit.factory.stage6.round-robin.v1", "next_index": 0}
    if (state.get("schema") != "saeit.factory.stage6.round-robin.v1"
            or type(state.get("next_index")) is not int
            or state["next_index"] < 0):
        raise RuntimeError("STAGE6_CURSOR_INVALID")
    total = len(names)
    start = state["next_index"] % total if total else 0
    count = min(batch, total)
    chosen = [names[(start + i) % total] for i in range(count)]
    next_state = {"schema": "saeit.factory.stage6.round-robin.v1",
                  "next_index": (start + count) % total if total else 0}
    return chosen, cursor_path, next_state


def execute(root, lib, stage5, batch=300, only_order_id=None, excluded_orders=None):
    if only_order_id is not None and (not isinstance(only_order_id, str)
                                   or re.fullmatch(r"WO-[0-9]{8}", only_order_id) is None):
        raise RuntimeError("STAGE6_TARGET_ORDER_INVALID")
    root = Path(root).expanduser().resolve()
    if not root.is_dir():
        raise RuntimeError("STAGE6_PRIVATE_ROOT_MISSING")
    area = root / "production-instructions"
    lib.private_dir(area / "stage-06" / "technical-preflight")
    lib.private_dir(area / "stage-05" / "substantive-rework-inbox")
    lib.private_dir(area / "stage-06" / "blocked")
    lock = area / ".stage6-preflight.lock"
    if lock.is_symlink():
        raise RuntimeError("STAGE6_UNSAFE_LOCK")
    with lock.open("a+b") as guard:
        os.fchmod(guard.fileno(), 0o600)
        fcntl.flock(guard.fileno(), fcntl.LOCK_EX)
        queue = area / "stage-06" / "inbox"
        if queue.is_symlink() or not queue.is_dir():
            raise RuntimeError("STAGE6_UNSAFE_INBOX")
        names = sorted(p.name for p in queue.iterdir()
                       if p.is_file() and not p.is_symlink() and lib.NAME.fullmatch(p.name)
                       and (excluded_orders is None or
                            p.name.split("--r", 1)[0] not in excluded_orders))
        selected, cursor_path, next_state = fair_batch(area, names, batch, lib)
        if only_order_id is not None:
            selected = [name for name in names if name.startswith(only_order_id + "--r")][:batch]
            next_state = lib.read(cursor_path) if cursor_path.exists() else {
                "schema": "saeit.factory.stage6.round-robin.v1", "next_index": 0}
        created, blocked = 0, 0
        for name in selected:
            try:
                created += int(preflight(area, name, lib, stage5))
            except (RuntimeError, ValueError, KeyError, TypeError, OSError, UnicodeError) as exc:
                blocked += 1
                lib.atomic(area / "stage-06" / "blocked" / name, {
                    "order_file": name, "stage": 6,
                    "reason": type(exc).__name__ + ":" + str(exc)[:180],
                    "requires_evidence_repair": True, "stage7_authorized": False,
                    "quality1000_approved": False})
        lib.atomic(cursor_path, next_state)
        result = {
            "stage6_inbox": len(names),
            "stage6_technical_preflights_created_this_tick": created,
            "stage6_integrity_blocked_this_tick": blocked,
            "stage6_technical_preflights_total": len(list((area / "stage-06" / "technical-preflight").glob("WO-*.json"))),
            "stage5_substantive_rework_requests_total": len(list((area / "stage-05" / "substantive-rework-inbox").glob("WO-*.json"))),
            "stage6_independent_scientific_reviews_completed_by_worker": 0,
            "stage7_approved_handoffs_created": 0,
            "quality1000_certifications_created": 0,
            "public_releases_created": 0,
            "websites_modified": False,
        }
        lib.atomic(area / "stage-06" / "autonomous-status.json", result)
        return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--factory-private", required=True)
    parser.add_argument("--stage34-worker", required=True)
    parser.add_argument("--stage5-worker", required=True)
    parser.add_argument("--batch", type=int, default=300)
    parser.add_argument("--only-order-id")
    parser.add_argument("--exclude-owner-agri200", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.batch <= 1000:
        raise SystemExit("STAGE6_BATCH_RANGE")
    lib = dependency(args.stage34_worker, "stage34_private_for_stage6")
    stage5 = dependency(args.stage5_worker, "stage5_private_for_stage6")
    if args.only_order_id and args.exclude_owner_agri200:
        raise RuntimeError("STAGE6_CONFLICTING_SCOPE")
    if args.exclude_owner_agri200:
        from factory_strict_serial_scope_v1 import owner_agri200_ids
        excluded = owner_agri200_ids(args.factory_private)
    else:
        excluded = None
    print(json.dumps(execute(args.factory_private, lib, stage5, args.batch,
                             only_order_id=args.only_order_id, excluded_orders=excluded),
                     sort_keys=True, ensure_ascii=False))


if __name__ == "__main__":
    main()
