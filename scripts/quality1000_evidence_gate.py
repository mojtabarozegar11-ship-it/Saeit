#!/usr/bin/env python3
"""Version-bound 100x10 quality *rework* gate for real VPS factory receipts.

Checksums and internal QA cannot certify professional quality or release.
Signed independent approval is checked separately with an operator-pinned key.
"""
import hashlib
import re
from factory_quality_1000_v2 import require_no_false_certification, CRITERIA

HEX = re.compile(r"^[a-f0-9]{64}$")
SLUG = re.compile(r"^[a-z][a-z0-9_]{1,65}$")

def inspect(assessment, assessment_bytes, order):
    if (not isinstance(assessment, dict)
            or assessment.get("schema") != "saeit.factory.quality-rework.v2"
            or not isinstance(assessment_bytes, bytes)
            or not isinstance(order, dict)
            or order.get("schema") != "saeit.factory.production-rework-order.v1"):
        raise ValueError("QUALITY1000_INVALID_INPUT_SCHEMA")
    slug = assessment.get("recipe")
    digest = assessment.get("artifact_sha256")
    if (not isinstance(slug, str) or not SLUG.fullmatch(slug)
            or not isinstance(digest, str) or not HEX.fullmatch(digest)
            or order.get("recipe") != slug or order.get("artifact_sha256") != digest
            or order.get("source_quality_receipt_sha256")
                 != hashlib.sha256(assessment_bytes).hexdigest()):
        raise ValueError("QUALITY1000_SOURCE_ORDER_NOT_BOUND")
    if (assessment.get("commercial_release_allowed") is not False
            or assessment.get("premium_quality_approved") is not False
            or order.get("commercial_publish_allowed") is not False
            or order.get("owner_release_approval_required") is not True
            or order.get("signed_external_quality_approval_required") is not True):
        raise ValueError("QUALITY1000_UNSAFE_RELEASE_CLAIM")
    card = assessment.get("quality_1000_scorecard")
    if not isinstance(card, dict):
        raise ValueError("QUALITY1000_SCORECARD_MISSING")
    require_no_false_certification(card)
    if (card.get("artifact_sha256") != digest
            or assessment.get("quality_group_count") != 100
            or assessment.get("quality_points_per_group") != 10
            or assessment.get("required_quality_points") != 1000
            or assessment.get("quality_points_verified") is not None):
        raise ValueError("QUALITY1000_SCORECARD_WRONG_ARTIFACT_OR_POLICY")
    pending = [code for code in CRITERIA
               if card["criteria"][code]["documentary_points"] != 10]
    defects = assessment.get("defects")
    if not isinstance(defects, list) or any(not isinstance(x, str) for x in defects):
        raise ValueError("QUALITY1000_INVALID_DEFECTS")
    if len(set(defects)) != len(defects):
        raise ValueError("QUALITY1000_DUPLICATE_DEFECTS")
    return {
        "schema": "saeit.quality1000.bound-rework-inspection.v2",
        "recipe": slug,
        "family_id": assessment.get("family_id"),
        "artifact_sha256": digest,
        "assessment_sha256": hashlib.sha256(assessment_bytes).hexdigest(),
        "criteria_count": 100,
        "documentary_points": card["documentary_evidence_points"],
        "missing_documentary_groups": pending,
        "unresolved_defects": sorted(defects),
        "technical_rework_needed": bool(pending or defects),
        "independent_professional_grade": None,
        "signed_quality_1000_certified": False,
        "owner_publication_approval_verified": False,
        "publication_allowed": False,
        "next_gate": ("repair_and_retest" if pending or defects else
                      "independent_authenticated_signed_review"),
    }
