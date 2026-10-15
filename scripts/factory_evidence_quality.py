#!/usr/bin/env python3
"""Offline factory evidence completeness assessment, never commercial approval.

Consumes the *existing* factory research bundle. This does not gather evidence,
forge citations, verify truth, change records, call an API, or approve release.
A 100% evidence-completeness signal is still only a request for human review.
Python 3.8+; stdlib only.
"""
import hashlib
import ipaddress
import math
import re
from collections import Counter
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit

MIN_EXTERNAL_DOMAINS = 5
MIN_VALID_EVIDENCE = 100
MIN_VERIFIED_INTERNAL_ACTIONS = 1
PASS_OUTCOMES = frozenset(("PASS", "APPROVED"))
REQUIRED_FACTORS = (
    "market_demand", "willingness_to_pay", "expected_revenue_potential",
    "expected_profit_potential", "build_cost_efficiency",
    "operating_cost_efficiency", "execution_feasibility", "legal_safety",
    "security_safety", "independent_source_coverage",
)
TWO_PART_SUFFIXES = frozenset(("co.uk", "gov.uk", "ac.uk", "org.uk",
                                 "com.au", "gov.au", "co.jp"))


def independent_domain(raw_url):
    """Return conservative public HTTPS origin group or None.

    Reject private and numerical hosts, URL credentials and unsafe syntax.
    This verifies only a URL shape, never factual reliability or legal rights.
    """
    if not isinstance(raw_url, str) or len(raw_url) > 2048:
        return None
    try:
        parsed = urlsplit(raw_url.strip())
        host = parsed.hostname
        port = parsed.port
    except ValueError:
        return None
    if parsed.scheme != "https" or parsed.username is not None or parsed.password is not None:
        return None
    if port not in (None, 443) or not host or len(host) > 253 or host.endswith("."):
        return None
    if host.lower() in {"localhost", "localhost.localdomain"}:
        return None
    try:
        ipaddress.ip_address(host)
        return None
    except ValueError:
        pass
    labels = host.lower().split(".")
    if len(labels) < 2 or any(not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", item)
                               for item in labels):
        return None
    if labels[-1].isdigit() or len(labels[-1]) < 2:
        return None
    suffix = ".".join(labels[-2:])
    return ".".join(labels[-3:]) if suffix in TWO_PART_SUFFIXES and len(labels) >= 3 else suffix


def _confidence(value):
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return False
    return number.is_finite() and Decimal("0.70") <= number <= Decimal("1")


def _clean_text(value):
    if not isinstance(value, str):
        return ""
    return " ".join(value.split()).casefold()


def _verified_internal_action(item):
    if not isinstance(item, dict):
        return False
    digest = item.get("evidence_sha256")
    identifier = item.get("action_id")
    return (
        item.get("verified") is True
        and isinstance(identifier, str) and bool(re.fullmatch(r"[A-Za-z0-9_.:-]{8,100}", identifier))
        and isinstance(digest, str) and bool(re.fullmatch(r"[a-f0-9]{64}", digest))
        and isinstance(item.get("outcome"), str) and len(item["outcome"].strip()) >= 24
    )


def assess(bundle):
    if not isinstance(bundle, dict):
        raise ValueError("RESEARCH_BUNDLE_OBJECT_REQUIRED")
    raw_sources = bundle.get("sources") if isinstance(bundle.get("sources"), list) else []
    raw_evidence = bundle.get("evidence") if isinstance(bundle.get("evidence"), list) else []
    raw_actions = bundle.get("internal_actions") if isinstance(bundle.get("internal_actions"), list) else []
    issues = set(str(x) for x in bundle.get("issues", []) if isinstance(x, str))
    missing = set(str(x) for x in bundle.get("missing_factors", []) if isinstance(x, str))
    domains = set()
    source_ids = set()
    sources_by_domain = {}
    for source in raw_sources:
        if not isinstance(source, dict):
            continue
        host = independent_domain(source.get("url"))
        ident = source.get("id")
        if host and isinstance(ident, int) and not isinstance(ident, bool) and ident > 0:
            domains.add(host)
            source_ids.add(ident)
            sources_by_domain[ident] = host

    unique_evidence = {}
    source_coverage = set()
    for e in raw_evidence:
        if not isinstance(e, dict) or e.get("source_id") not in source_ids:
            continue
        passage = _clean_text(e.get("passage"))
        if len(passage) < 80 or not _confidence(e.get("confidence")):
            continue
        digest = hashlib.sha256(passage.encode("utf-8")).hexdigest()
        if digest not in unique_evidence:
            unique_evidence[digest] = e
            source_coverage.add(sources_by_domain[e["source_id"]])

    action_ids = set()
    for action in raw_actions:
        if _verified_internal_action(action):
            action_ids.add(action["action_id"])
    outcome_passed = str(bundle.get("validation_outcome") or "").upper() in PASS_OUTCOMES
    missing_factors = tuple(x for x in REQUIRED_FACTORS if x in missing)
    # A factor not listed as missing is not positively verified merely because
    # metadata omits the key. Require an upstream PASS result for factor credit.
    factor_count = (len(REQUIRED_FACTORS) - len(missing_factors)) if outcome_passed else 0
    no_active_or_owner_problem = "ALREADY_ACTIVE" not in issues and "MISSING_PRODUCT_OWNER" not in issues
    complete_external = len(domains) >= MIN_EXTERNAL_DOMAINS and len(source_coverage) >= MIN_EXTERNAL_DOMAINS
    complete_evidence = len(unique_evidence) >= MIN_VALID_EVIDENCE
    complete_internal = len(action_ids) >= MIN_VERIFIED_INTERNAL_ACTIONS
    research_ready = bool(complete_external and complete_evidence and complete_internal
                          and outcome_passed and not missing_factors and no_active_or_owner_problem)

    # Coverage is only a workload indicator, NOT an 0-100 judgment of utility.
    metric = (
        25 * min(1.0, len(domains) / MIN_EXTERNAL_DOMAINS)
        + 10 * min(1.0, len(source_coverage) / MIN_EXTERNAL_DOMAINS)
        + 35 * min(1.0, len(unique_evidence) / MIN_VALID_EVIDENCE)
        + 10 * min(1.0, len(action_ids) / MIN_VERIFIED_INTERNAL_ACTIONS)
        + 20 * (factor_count / len(REQUIRED_FACTORS))
    )
    blockers = []
    if not complete_external:
        blockers.append("FIVE_DISTINCT_PUBLIC_SOURCES_WITH_LINKED_EVIDENCE_REQUIRED")
    if not complete_evidence:
        blockers.append("ONE_HUNDRED_DISTINCT_STRONG_EVIDENCE_PASSAGES_REQUIRED")
    if not complete_internal:
        blockers.append("ONE_STRUCTURED_INTERNAL_RESEARCH_ACTION_REQUIRED")
    if not outcome_passed or missing_factors:
        blockers.append("TEN_FACTOR_VALIDATION_PASS_REQUIRED")
    if not no_active_or_owner_problem:
        blockers.append("FACTORY_OWNER_OR_ACTIVE_PRODUCT_STATE_INVALID")
    if "NO_APPROVED_KNOWLEDGE_ARTICLE" in issues:
        blockers.append("PUBLISHED_KNOWLEDGE_PROVENANCE_REQUIRED")
    if "NO_POSITIVE_PRICE" in issues:
        blockers.append("FAIR_PRICE_AND_COST_REVIEW_REQUIRED")
    blockers.append("HUMAN_COMMERCIAL_LICENSE_AND_FACTUAL_REVIEW_REQUIRED")

    return {
        "schema": "saeit.factory.research-readiness.v1",
        "product_id": bundle.get("product_id"),
        "research_gate": "QUANTITATIVE_THRESHOLD_MET_REVIEW_REQUIRED" if research_ready else "RESEARCH_BLOCKED",
        "research_gate_passed": research_ready,
        "evidence_completeness_workload_percent": round(metric, 1),
        "counts": {
            "public_distinct_domain_groups": len(domains),
            "public_domains_with_strong_evidence": len(source_coverage),
            "validated_unique_evidence_passages": len(unique_evidence),
            "self_attested_internal_action_records": len(action_ids),
            "upstream_factors_marked_missing": len(missing_factors),
        },
        "targets": {
            "public_independent_sources": MIN_EXTERNAL_DOMAINS,
            "verified_evidence_passages": MIN_VALID_EVIDENCE,
            "verified_internal_actions": MIN_VERIFIED_INTERNAL_ACTIONS,
            "required_validation_factors": len(REQUIRED_FACTORS),
        },
        "blockers": blockers,
        "publish_authorized": False,
        "commercial_quality_approved": False,
        "price_review_completed": False,
        "verified_sales": False,
        "note": "Candidate URLs, passages and internal-action flags are NOT independently authenticated. Counts are workload indicators only; human verification is mandatory. No automatic publication is permitted.",
    }
