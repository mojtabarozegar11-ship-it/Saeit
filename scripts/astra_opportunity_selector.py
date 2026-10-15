#!/usr/bin/env python3
"""Astra 2.0: offline, evidence-aware opportunity PRIORITIZATION only.

This is a safe selection prototype, not a research provider or manufacturing
dispatcher. Input snapshots are caller-supplied and NOT independently attested;
therefore no candidate can be promoted to build, publish or charge by this code.
No external APIs, credentials, website databases, or product files are accessed.
"""
import argparse
from datetime import datetime, timezone, timedelta
import ipaddress
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

WEIGHTS = {
    "problem_intensity": 20,
    "demand": 20,
    "differentiation": 15,
    "feasibility": 15,
    "margin": 15,
    "distribution": 10,
    "strategic_fit": 5,
}
CLAIM_TYPES = frozenset(("problem", "willingness_to_pay", "comparison", "feasibility"))
REQUIRED_GATE_NAMES = (
    "lawful", "rights_reviewed", "build_capability_available",
    "distribution_path_available",
)
MAX_SNAPSHOT_AGE_DAYS = 120
MIN_RESEARCH_PRIORITY_SCORE = 60.0
MIN_DISTINCT_SOURCE_DOMAINS = 3
MAX_OPPORTUNITIES = 2000
MAX_SNAPSHOTS = 10000


def _utc(iso):
    if not isinstance(iso, str):
        raise ValueError("timestamp must be ISO8601 string")
    stamp = iso.replace("Z", "+00:00")
    value = datetime.fromisoformat(stamp)
    if value.tzinfo is None:
        raise ValueError("timestamp must be timezone aware")
    return value.astimezone(timezone.utc)


def _public_https_domain(url):
    """URL hygiene only, never a claim that a remote resource is safe to fetch."""
    if not isinstance(url, str) or len(url) > 2048:
        return None
    try:
        parsed = urlsplit(url)
        host = parsed.hostname
        if (parsed.scheme.lower() != "https" or not host or
                parsed.username is not None or parsed.password is not None or
                parsed.fragment or parsed.port not in (None, 443)):
            return None
        host = host.rstrip(".").lower()
        if (len(host) > 253 or "." not in host or host == "localhost" or
                host.endswith((".localhost", ".local", ".internal", ".test", ".invalid"))):
            return None
        try:
            ipaddress.ip_address(host)
            return None  # IP-literal links are never accepted as citations
        except ValueError:
            pass
        if not re.fullmatch(r"[a-z0-9.-]+", host):
            return None
        if any(not label or len(label) > 63 or label.startswith("-") or
               label.endswith("-") for label in host.split(".")):
            return None
        return host
    except (ValueError, TypeError):
        return None


def _validated_sources(snapshots, now):
    """Return eligible *source references*, not trusted facts or buying demand."""
    refs = {}
    if not isinstance(snapshots, list) or len(snapshots) > MAX_SNAPSHOTS:
        raise ValueError("invalid snapshot batch")
    for s in snapshots:
        if not isinstance(s, dict) or not isinstance(s.get("opportunity_key"), str):
            continue
        key = s["opportunity_key"]
        domain = _public_https_domain(s.get("url"))
        digest = s.get("content_sha256")
        claim = s.get("claim_type")
        if not (domain and isinstance(digest, str) and
                re.fullmatch(r"[a-fA-F0-9]{64}", digest) and claim in CLAIM_TYPES):
            continue
        try:
            seen = _utc(s.get("observed_at"))
        except (ValueError, TypeError, OverflowError):
            continue
        if not now - timedelta(days=MAX_SNAPSHOT_AGE_DAYS) <= seen <= now:
            continue
        # One host is one preliminary domain, not independently corroborated
        # proof of customer demand or independent publisher identity.
        refs.setdefault(key, {}).setdefault(domain, set()).add(claim)
    return refs


def _check_candidate(candidate):
    if not isinstance(candidate, dict):
        raise ValueError("candidate must be an object")
    key = candidate.get("opportunity_key")
    if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}", key):
        raise ValueError("invalid opportunity_key")
    title = candidate.get("problem")
    if not isinstance(title, str) or not title.strip() or len(title) > 500:
        raise ValueError("specific non-empty problem required")
    measures = candidate.get("assessments")
    if not isinstance(measures, dict) or set(measures) != set(WEIGHTS):
        raise ValueError("all seven assessments required")
    if any(type(measures[k]) is not int or not 0 <= measures[k] <= 100 for k in WEIGHTS):
        raise ValueError("assessment must be integer 0..100")
    gates = candidate.get("gates")
    if not isinstance(gates, dict) or set(gates) != set(REQUIRED_GATE_NAMES):
        raise ValueError("exact named hard gates required")
    if any(type(gates[k]) is not bool for k in gates):
        raise ValueError("hard gates must be booleans")
    return key, title.strip(), measures, gates


def rank_opportunities(candidates, snapshots, now_utc):
    """Produce review-only ranked dossiers; *never* an executable build queue.

    A dossier can reach review only with problem, willingness-to-pay,
    comparison, and feasibility claims across at least three source domains.
    Its provisional priority score must also clear the research floor. These
    checks improve topic triage; they do not attest the supplied sources or
    qualify a product for manufacture, publication, or payment.
    """
    now = _utc(now_utc) if isinstance(now_utc, str) else now_utc
    if not isinstance(now, datetime) or now.tzinfo is None:
        raise ValueError("now_utc must be a timezone-aware datetime")
    now = now.astimezone(timezone.utc)
    if not isinstance(candidates, list) or len(candidates) > MAX_OPPORTUNITIES:
        raise ValueError("invalid candidate batch")
    sources = _validated_sources(snapshots, now)
    out, seen = [], set()
    for item in candidates:
        key, problem, dimensions, gates = _check_candidate(item)
        if key in seen:
            raise ValueError("duplicate opportunity_key")
        seen.add(key)
        domains = sources.get(key, {})
        claim_types = set().union(*domains.values()) if domains else set()
        claim_domains = {
            claim: {domain for domain, claims in domains.items() if claim in claims}
            for claim in CLAIM_TYPES
        }
        # A high self-reported score cannot compensate for weak topic evidence.
        score = sum(WEIGHTS[k] * dimensions[k] for k in WEIGHTS) / 100
        reasons = []
        if not gates["lawful"] or not gates["rights_reviewed"]:
            status = "REJECTED"
            reasons.append("LEGAL_OR_RIGHTS_GATE_FAILED")
        elif not gates["build_capability_available"] or not gates["distribution_path_available"]:
            status = "RESEARCH_REQUIRED"
            reasons.append("BUILD_OR_DISTRIBUTION_CAPABILITY_MISSING")
        elif score < MIN_RESEARCH_PRIORITY_SCORE:
            status = "RESEARCH_REQUIRED"
            reasons.append("PROVISIONAL_PRIORITY_BELOW_RESEARCH_FLOOR")
        elif len(domains) < MIN_DISTINCT_SOURCE_DOMAINS:
            status = "RESEARCH_REQUIRED"
            reasons.append("FEWER_THAN_THREE_DISTINCT_SOURCE_DOMAINS")
        else:
            missing = sorted(CLAIM_TYPES - claim_types)
            if missing:
                status = "RESEARCH_REQUIRED"
                if "problem" in missing or "willingness_to_pay" in missing:
                    reasons.append("PROBLEM_OR_WILLINGNESS_SIGNAL_MISSING")
                if "comparison" in missing:
                    reasons.append("COMPETITOR_COMPARISON_SIGNAL_MISSING")
                if "feasibility" in missing:
                    reasons.append("FEASIBILITY_SIGNAL_MISSING")
            else:
                status = "REVIEW_REQUIRED"
                reasons.append("SOURCE_AND_ASSESSMENT_ATTESTATION_REQUIRED")
        # Source references and self-reported assessments remain provisional;
        # neither is a probability, verified commercial value, or QA score.
        out.append({
            "opportunity_key": key,
            "problem": problem,
            "status": status,
            "priority_score": round(score, 2),
            "distinct_source_domains_preliminary": len(domains),
            "claim_source_domains_preliminary": {
                claim: len(claim_domains[claim]) for claim in sorted(CLAIM_TYPES)
            },
            "research_priority_floor": MIN_RESEARCH_PRIORITY_SCORE,
            "observed_claim_types": sorted(claim_types),
            "blockers": reasons,
            "build_authorized": False,
            "publish_authorized": False,
            "payment_authorized": False,
            "evidence_verified_independently": False,
            "assessments_are_provisional": True,
        })
    order = {"REVIEW_REQUIRED": 0, "RESEARCH_REQUIRED": 1, "REJECTED": 2}
    out.sort(key=lambda x: (order[x["status"]], -x["priority_score"], x["opportunity_key"]))
    return {
        "schema_version": 1,
        "selector_mode": "offline_provisional_review_only",
        "network_calls": 0,
        "paid_calls": 0,
        "production_mutations": 0,
        "new_products_built": 0,
        "candidates": out,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Local candidate/snapshot JSON")
    parser.add_argument("--output", required=True, help="Local review JSON; not a build manifest")
    parser.add_argument("--now-utc", required=True, help="ISO8601 evaluation clock for reproducibility")
    args = parser.parse_args(argv)
    source = Path(args.input).resolve()
    if not source.is_file() or source.is_symlink() or source.stat().st_size > 5_000_000:
        raise ValueError("unsafe/missing input file")
    data = json.loads(source.read_text(encoding="utf-8"))
    report = rank_opportunities(data["candidates"], data["snapshots"], args.now_utc)
    output = Path(args.output).resolve()
    if source == output or output.is_symlink() or not output.parent.is_dir():
        raise ValueError("invalid output path")
    # Local, explicit review result only. Never writes to factory runtime or websites.
    import os
    import tempfile
    fd, temp = tempfile.mkstemp(prefix=".astra-selector-", dir=str(output.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(report, stream, indent=2, ensure_ascii=False, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temp, 0o600)
        os.replace(temp, output)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
    print("ASTRA_SELECTOR_STATUS=REVIEW_ONLY")
    print("ASTRA_SELECTOR_CANDIDATES=" + str(len(report["candidates"])))
    print("ASTRA_SELECTOR_BUILD_AUTHORIZED=false")


if __name__ == "__main__":
    main()
