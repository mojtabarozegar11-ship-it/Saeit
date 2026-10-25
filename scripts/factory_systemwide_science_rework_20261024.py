#!/usr/bin/env python3
"""Factory-wide science remediation: translate EVERY private v003 into source-level work.

This is a systemic Stage-2 evidence-repair bridge, NOT another QC approval.
It neither rewrites old files nor pretends indexed abstracts are primary full text.
New orders are discovered dynamically; all existing 184 are processed in one pass.
"""
import argparse
from collections import Counter
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile

SCHEMA = "saeit.factory.scientific-source-repair.v1"
NAME = re.compile(r"WO-[0-9]{8}--r[0-9]{3}\.json\Z")
SHA = re.compile(r"[a-f0-9]{64}\Z")
DOI = re.compile(r"10\.[0-9]{4,9}/[-._;()/:A-Za-z0-9]+\Z")

class Blocked(ValueError):
    pass

def ensure(condition, code):
    if not condition:
        raise Blocked(code)

def digest(data):
    return hashlib.sha256(data).hexdigest()

def canonical(obj):
    return (json.dumps(obj, sort_keys=True, ensure_ascii=False,
                       separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")

def read(path):
    ensure(path.is_file() and not path.is_symlink() and 0 < path.stat().st_size <= 2_000_000,
           "EVIDENCE_MISSING_OR_UNSAFE")
    return json.loads(path.read_text("utf-8"))

def private_dir(path):
    ensure(not path.is_symlink(), "UNSAFE_DIRECTORY_LINK")
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    ensure(path.is_dir() and not path.is_symlink(), "UNSAFE_DIRECTORY")

def once(path, obj):
    raw = canonical(obj)
    private_dir(path.parent)
    ensure(not path.is_symlink(), "EVIDENCE_SYMLINK")
    if path.exists():
        ensure(path.is_file() and path.read_bytes() == raw, "IMMUTABLE_PACKET_CONFLICT")
        return False
    fd, tmp = tempfile.mkstemp(prefix=".science-req-", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(tmp, path)
        except FileExistsError:
            ensure(path.is_file() and not path.is_symlink()
                   and path.read_bytes() == raw, "IMMUTABLE_PACKET_CONFLICT")
            return False
        return True
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)

def validated(area, name):
    ensure(NAME.fullmatch(name) is not None, "ORDER_FILE_INVALID")
    man = read(area / "stage-05/source-grounded-v003-manifests" / name)
    qc = read(area / "stage-06/source-grounded-v003-qc" / name)
    review = read(area / "stage-06/scientific-review-inbox-v003" / name)
    research = read(area / "stage-02/completed-dossiers" / name)
    ensure(man.get("artifact_revision") == 3 and man.get("order_file") == name
           and man.get("source_revision") == research.get("revision")
           and man.get("order_id") == research.get("order_id")
           and qc.get("revision") == 3
           and qc.get("mechanical_integrity_pass") is True
           and qc.get("artifact_sha256") == man.get("zip_sha256")
           and review.get("artifact_sha256") == man.get("zip_sha256")
           and review.get("scientific_review_state") ==
               "PENDING_INDEPENDENT_VERIFIED_EVIDENCE"
           and review.get("quality1000_approved") is False
           and qc.get("independent_quality1000_approved") is False
           and man.get("public_distribution_allowed") is False
           and man.get("quality1000_approved") is False,
           "RESEARCH_REVISION_OR_FAIL_CLOSED_QC_INVALID")
    sources, claims = research.get("sources"), research.get("claims")
    ensure(isinstance(sources, list) and len(sources) >= 4
           and isinstance(claims, list) and len(claims) >= 5,
           "SOURCE_EVIDENCE_INCOMPLETE")
    source_by_id = {}
    for source in sources:
        ensure(isinstance(source, dict) and isinstance(source.get("id"), str)
               and source["id"] not in source_by_id
               and isinstance(source.get("title"), str)
               and isinstance(source.get("url"), str),
               "MALFORMED_SOURCE")
        source_by_id[source["id"]] = source
    claim_ids = set()
    outbound = {sid: [] for sid in source_by_id}
    claim_packets = []
    for claim in claims:
        ensure(isinstance(claim, dict) and isinstance(claim.get("id"), str)
               and claim["id"] not in claim_ids
               and isinstance(claim.get("statement"), str)
               and isinstance(claim.get("source_ids"), list)
               and 1 <= len(claim["source_ids"]) <= 5
               and all(sid in source_by_id for sid in claim["source_ids"]),
               "CLAIM_TO_SOURCE_LINK_INVALID")
        claim_ids.add(claim["id"])
        for sid in claim["source_ids"]:
            outbound[sid].append(claim["id"])
        claim_packets.append({"claim_id": claim["id"], "indexed_abstract_statement":
            claim["statement"], "source_ids": claim["source_ids"],
            "original_fulltext_support": "NOT_VERIFIED",
            "agronomic_safety_and_transferability": "NOT_VERIFIED"})
    ensure(set(man.get("source_ids", [])) == set(source_by_id)
           and set(man.get("claim_ids", [])) == claim_ids,
           "V003_RESEARCH_PROVENANCE_MISMATCH")
    tasks = []
    for sid, source in sorted(source_by_id.items()):
        doi_url = source.get("doi")
        doi = (doi_url.removeprefix("https://doi.org/") if isinstance(doi_url, str)
               else "")
        if doi:
            ensure(DOI.fullmatch(doi) is not None, "SOURCE_DOI_INVALID")
        tasks.append({
            "source_id": sid, "title": source["title"],
            "publisher": source.get("publisher"), "source_url": source["url"],
            "doi": doi or None,
            "source_medium": source.get("source_medium", "UNVERIFIED"),
            "indexed_abstract_sha256": source.get("abstract_sha256"),
            "linked_claim_ids": sorted(outbound[sid]),
            "required_action": "FETCH_LICENSABLE_PRIMARY_FULLTEXT_AND_CHECK_EXACT_PASSAGES",
            "original_fulltext_retrieved": False,
            "retraction_and_license_checked": False,
            "exact_supporting_pages_verified": False,
        })
    owner = area / "stage-05/owner-rework-20261024" / name
    owner_hash = None
    if owner.exists():
        decision = read(owner)
        ensure(decision.get("owner_decision") == "REJECT_RETURN_TO_STAGE5_REWORK"
               and decision.get("quality1000_approved") is False,
               "OWNER_REJECTION_INVALID")
        owner_hash = digest(owner.read_bytes())
    return {
        "schema": SCHEMA, "order_file": name, "order_id": man["order_id"],
        "source_product_id": research.get("source_product_id"),
        "artifact_revision": 3, "artifact_sha256": man["zip_sha256"],
        "research_sha256": digest(canonical(research).rstrip(b"\n")),
        "revision_manifest_sha256": digest(canonical(man).rstrip(b"\n")),
        "owner_rejection_receipt_sha256": owner_hash,
        "scientific_inbox_sha256": digest(canonical(review).rstrip(b"\n")),
        "claimed_product_status": "REJECTED_AWAITING_SUBSTANTIVE_EVIDENCE",
        "scientific_primary_source_tasks": tasks, "scientific_claims": claim_packets,
        "mandatory_next_stage": "STAGE2_PRIMARY_FULLTEXT_AND_CLAIM_VERIFICATION",
        "reviewer_must_sign_version_bound_verdict": True,
        "all_claims_verified": False, "independent_review_completed": False,
        "qc1000_approved": False, "commercial_release": False,
        "public_distribution_allowed": False,
        "do_not_copy_selling_products_or_mutate_prior_versions": True
    }

def execute(root, batch=2000, dry_run=False, excluded_orders=None):
    area = Path(root).resolve() / "production-instructions"
    source = area / "stage-05/source-grounded-v003-manifests"
    ensure(area.is_dir() and not area.is_symlink()
           and source.is_dir() and not source.is_symlink(), "PRIVATE_FACTORY_INPUT_UNSAFE")
    names = sorted(p.name for p in source.iterdir()
                   if p.is_file() and not p.is_symlink() and NAME.fullmatch(p.name)
                   and (excluded_orders is None or
                        p.name.split("--r", 1)[0] not in excluded_orders))
    if excluded_orders is None:
        ensure(names, "EMPTY_REWORK_COHORT")
    if dry_run:
        packets = [validated(area, name) for name in names]
        return {"schema": SCHEMA, "checked": len(packets), "written": 0,
                "source_tasks": sum(len(x["scientific_primary_source_tasks"]) for x in packets),
                "release_approvals": 0, "dry_run": True}
    directory = area / "stage-02/primary-fulltext-repair-inbox"
    private_dir(directory)
    lock = directory / ".systemwide-source-repair.lock"
    ensure(not lock.is_symlink(), "UNSAFE_LOCK")
    count = Counter()
    with lock.open("a+b") as stream:
        os.fchmod(stream.fileno(), 0o600)
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        # Dynamic cohort, no "first five", no 250-item starvation:
        # every known private v003 is visited; batch is a bounded safety cap.
        ensure(len(names) <= batch, "BATCH_LIMIT_REQUIRES_INCREASE_NOT_SILENT_TRUNCATION")
        for name in names:
            try:
                packet = validated(area, name)
                count["checked"] += 1
                count["source_tasks"] += len(packet["scientific_primary_source_tasks"])
                count["new_requests"] += int(once(directory / name, packet))
            except (ValueError, OSError, TypeError, KeyError, UnicodeError) as exc:
                count["blocked"] += 1
                private_dir(area / "stage-02/primary-fulltext-repair-blocked")
                path = area / "stage-02/primary-fulltext-repair-blocked" / name
                once(path, {"schema": SCHEMA, "order_file": name,
                            "reason": type(exc).__name__ + ":" + str(exc)[:160],
                            "qc1000_approved": False, "public_distribution_allowed": False})
        result = {"schema": SCHEMA, "dynamic_v003_cohort": len(names),
                  "checked": count["checked"], "new_requests": count["new_requests"],
                  "existing_requests_reverified": count["checked"]-count["new_requests"],
                  "blocked": count["blocked"], "source_tasks": count["source_tasks"],
                  "scientific_reviews_completed_by_this_worker": 0,
                  "qc1000_approvals": 0, "publications": 0,
                  "primary_fulltext_absence_is_a_real_bottleneck": True}
        ensure(count["blocked"] == 0, "SOURCE_REPAIR_HAS_BLOCKED_ORDERS")
        return result

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--factory-private", required=True)
    parser.add_argument("--batch", type=int, default=2000)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--exclude-owner-agri200", action="store_true")
    args = parser.parse_args()
    try:
        if args.exclude_owner_agri200:
            from factory_strict_serial_scope_v1 import owner_agri200_ids
            excluded = owner_agri200_ids(args.factory_private)
        else:
            excluded = None
        print(json.dumps(execute(args.factory_private, args.batch, args.dry_run,
                                 excluded_orders=excluded),
                         ensure_ascii=False, sort_keys=True), flush=True)
    except Exception as exc:
        print("SCIENCE_REPAIR_ERROR:" + type(exc).__name__ + ":" + str(exc)[:180],
              file=sys.stderr)
        raise SystemExit(1)
