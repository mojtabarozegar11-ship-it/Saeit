#!/usr/bin/env python3
"""Private, no-network go/no-go RESEARCH assessment for one Astra candidate.

This is NOT a customer attestation authority, crawler, product launch gate,
price setter or independent real-world verification mechanism. Source metadata
provided by the caller remains unverified. Release is always fail-closed.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import tempfile
from urllib.parse import urlsplit

MAX_INPUT_BYTES = 200_000
MAX_SOURCES = 300
MAX_COMPETITORS = 30
EXPECTED_SOURCE_FIELDS = {"id", "url", "role", "claim"}
EXPECTED_COMPETITOR_FIELDS = {"name", "source_ids", "features"}
ROLES = {"context", "direct_competitor", "technical_benchmark"}
CLAIMS = {"problem_context", "competitor_capability", "feasibility_context"}
FEATURE_STATES = {"documented_present", "not_assessed"}
FEATURES = {"water_land_allocation", "multi_year_planning", "crop_rotation",
            "irrigation_scheduling", "farm_margin_budget", "offline_access",
            "reproducible_audit_export"}
REQUIRED_GAPS = (
    "VERIFY_ACTUAL_BUYER_PROBLEM_IN_CONSENTED_INTERVIEWS",
    "VERIFY_WILLINGNESS_TO_PAY_WITH_REAL_BUYERS",
    "OBTAIN_INDEPENDENT_AGRONOMY_AND_ECONOMICS_REVIEW",
    "TEST_USABILITY_AND_ACCESSIBILITY_WITH_TARGET_USERS",
    "VERIFY_FIELD_INPUT_RIGHTS_AND_SOURCE_PROVENANCE",
    "PROVE_CLEAR_ADVANTAGE_VERSUS_EXISTING_FREE_TOOLS",
    "REVIEW_ORIGINALITY_LICENSE_SUPPORT_AND_MAINTENANCE",
    "RETEST_REAL_CHECKOUT_AND_DIGITAL_FULFILMENT",
)


def _host(url):
    """Public HTTPS *reference* hygiene, never permission to fetch a URL."""
    if not isinstance(url, str) or len(url) > 2048:
        return None
    try:
        p = urlsplit(url)
        host = p.hostname
        if (p.scheme != "https" or not host or p.username or p.password or
                p.fragment or p.port not in (None, 443)):
            return None
        host = host.lower().rstrip(".")
        if (len(host) > 253 or "." not in host or
                host.endswith((".local", ".internal", ".invalid", ".test")) or
                host == "localhost" or
                not re.fullmatch(r"[a-z0-9.-]+", host) or
                any(not label or label.startswith("-") or label.endswith("-")
                    for label in host.split("."))):
            return None
        # Never accept IP literals (IPv4 or IPv6), even if HTTPS formatted.
        import ipaddress
        try:
            ipaddress.ip_address(host)
        except ValueError:
            return host
        return None
    except (ValueError, TypeError):
        return None


def assess(data):
    if not isinstance(data, dict) or set(data) != {
            "product_key", "hypothesis", "observed_utc", "sources",
            "competitors"}:
        raise ValueError("exact five-field market research packet required")
    key = data["product_key"]
    if not isinstance(key, str) or not re.fullmatch(r"[a-z][a-z0-9_]{2,79}", key):
        raise ValueError("invalid product_key")
    if (not isinstance(data["hypothesis"], str) or
            not 15 <= len(data["hypothesis"].strip()) <= 800):
        raise ValueError("specific research hypothesis required")
    if not isinstance(data["observed_utc"], str):
        raise ValueError("UTC timestamp required")
    try:
        when = datetime.fromisoformat(data["observed_utc"].replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid UTC timestamp") from exc
    if when.tzinfo is None or when.utcoffset().total_seconds() != 0:
        raise ValueError("UTC timestamp required")
    srcs = data["sources"]
    if not isinstance(srcs, list) or len(srcs) > MAX_SOURCES:
        raise ValueError("bounded source list required")
    ids = {}
    urls = set()
    hosts = set()
    roles = set()
    for source in srcs:
        if not isinstance(source, dict) or set(source) != EXPECTED_SOURCE_FIELDS:
            raise ValueError("untrusted or malformed source metadata")
        identifier = source["id"]
        if (not isinstance(identifier, str) or
                not re.fullmatch(r"E[0-9]{2,4}", identifier) or identifier in ids):
            raise ValueError("duplicate or invalid source ID")
        host = _host(source["url"])
        if host is None or source["url"] in urls:
            raise ValueError("invalid or duplicate source URL")
        if source["role"] not in ROLES or source["claim"] not in CLAIMS:
            raise ValueError("invalid source classification")
        if source["role"] == "direct_competitor" and source["claim"] != "competitor_capability":
            raise ValueError("competitor citation is not a capability claim")
        if (source["role"] != "direct_competitor" and
                source["claim"] == "competitor_capability"):
            raise ValueError("capability source must be a direct competitor")
        ids[identifier] = source
        urls.add(source["url"])
        hosts.add(host)
        roles.add(source["role"])
    comparisons = data["competitors"]
    if not isinstance(comparisons, list) or len(comparisons) > MAX_COMPETITORS:
        raise ValueError("bounded competitor list required")
    names = set()
    competitor_domains = set()
    feature_coverage = set()
    for item in comparisons:
        if not isinstance(item, dict) or set(item) != EXPECTED_COMPETITOR_FIELDS:
            raise ValueError("invalid competitor matrix")
        name = item["name"]
        if not isinstance(name, str) or not 2 <= len(name.strip()) <= 120:
            raise ValueError("invalid competitor")
        if name.lower() in names:
            raise ValueError("duplicate competitor")
        names.add(name.lower())
        citations = item["source_ids"]
        if not isinstance(citations, list) or not citations or len(citations) > 20:
            raise ValueError("competitor requires primary source IDs")
        if len(set(citations)) != len(citations) or any(
                source_id not in ids or ids[source_id]["role"] != "direct_competitor"
                for source_id in citations):
            raise ValueError("competitor lacks direct source evidence")
        feature_map = item["features"]
        if not isinstance(feature_map, dict) or not feature_map or (
                set(feature_map) - FEATURES) or any(
                    v not in FEATURE_STATES for v in feature_map.values()):
            # A missing feature must be NOT_ASSESSED, not assumed absent.
            raise ValueError("unsupported competitor feature claim")
        feature_coverage.update(feature_map)
        for source_id in citations:
            competitor_domains.add(_host(ids[source_id]["url"]))

    gaps = list(REQUIRED_GAPS)
    if len(competitor_domains) < 2:
        gaps.insert(0, "RESEARCH_AT_LEAST_TWO_DISTINCT_COMPETITOR_PUBLISHERS")
    if len(srcs) < 100:
        gaps.insert(0, "COLLECT_AND_INDEPENDENTLY_CHECK_100_PRODUCT_EVIDENCE_ITEMS")
    if len(feature_coverage) < 4:
        gaps.insert(0, "COMPLETE_SOURCE_GROUNDED_COMPETITOR_FEATURE_MATRIX")
    if "direct_competitor" not in roles:
        gaps.insert(0, "FIND_DIRECT_COMPETITION")
    return {
        "mode": "offline_private_market_research_only",
        "product_key": key,
        "sources_listed": len(srcs),
        "distinct_reference_hosts": len(hosts),
        "competitors_listed": len(comparisons),
        "distinct_competitor_publishers": len(competitor_domains),
        "compared_feature_dimensions": len(feature_coverage),
        "sources_independently_attested": 0,
        "real_buyer_interviews_attested": 0,
        "buyer_willingness_to_pay_verified": False,
        "professional_quality_score": None,
        "sale_price_verified": False,
        "commercial_release_status": "BLOCKED_AWAITING_INDEPENDENT_VALIDATION",
        "next_research_actions": gaps,
        "network_requests": 0,
        "factory_mutations": 0,
        "build_authorized": False,
        "publish_authorized": False,
        "payment_authorized": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    source = Path(args.input).expanduser()
    output = Path(args.output).expanduser()
    if source.is_symlink() or not source.is_file() or source.stat().st_size > MAX_INPUT_BYTES:
        raise ValueError("unsafe input")
    if output.is_symlink() or not output.parent.is_dir() or output.suffix != ".json":
        raise ValueError("unsafe output")
    source = source.resolve(strict=True)
    output = output.resolve()
    if source == output:
        raise ValueError("cannot overwrite source")
    result = assess(json.loads(source.read_text(encoding="utf-8")))
    payload = json.dumps(result, sort_keys=True, indent=2) + "\n"
    fd, tmp = tempfile.mkstemp(prefix=".astra-market-review-", dir=output.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            out.write(payload)
            out.flush()
            os.fsync(out.fileno())
        os.chmod(tmp, 0o600)
        os.replace(tmp, output)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    print("ASTRA_MARKET_REVIEW=RESEARCH_ONLY")
    print("ASTRA_MARKET_RELEASE_AUTHORIZED=false")


if __name__ == "__main__":
    main()
