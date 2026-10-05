"""Pure, versioned economic scoring and pre-build validation policies."""
from decimal import Decimal, InvalidOperation

from .factory_contracts import canonical_digest

RUBRIC_VERSION = "wealth-opportunity-v1"
VALIDATION_POLICY_VERSION = "cheap-validation-v1"
SOURCE_QUALITY_POLICY_VERSION = "source-quality-v1"

FACTOR_WEIGHTS = {
    "market_demand": Decimal("0.10"),
    "willingness_to_pay": Decimal("0.10"),
    "expected_revenue_potential": Decimal("0.08"),
    "expected_profit_potential": Decimal("0.10"),
    "time_to_first_revenue": Decimal("0.05"),
    "build_cost_efficiency": Decimal("0.06"),
    "operating_cost_efficiency": Decimal("0.05"),
    "execution_feasibility": Decimal("0.06"),
    "competition_position": Decimal("0.05"),
    "capital_efficiency": Decimal("0.06"),
    "legal_safety": Decimal("0.06"),
    "security_safety": Decimal("0.05"),
    "commercial_success_probability": Decimal("0.08"),
    "scalability": Decimal("0.05"),
    "defensibility": Decimal("0.05"),
}


def _factor_entries(records):
    by_factor = {key: [] for key in FACTOR_WEIGHTS}
    seen_sources = set()
    for record in records or []:
        quality = ((record.get("provenance") or {}).get("source_quality") or {})
        if quality.get("freshness") == "stale" or quality.get("duplicate") is True:
            continue
        source_id = str(record.get("source_identity") or record.get("source") or "")
        if not source_id or source_id in seen_sources:
            continue
        seen_sources.add(source_id)
        for factor, claim in (record.get("economic_factors") or {}).items():
            if factor not in by_factor or not isinstance(claim, dict):
                continue
            raw = claim.get("value")
            if raw is None:
                continue
            try:
                value = Decimal(str(raw))
            except (InvalidOperation, TypeError, ValueError):
                continue
            if not value.is_finite() or value < 0 or value > 100 or not str(claim.get("claim") or "").strip():
                continue
            by_factor[factor].append({
                "value": value, "source_id": source_id,
                "evidence_id": record.get("evidence_id"),
                "snapshot_digest": record.get("snapshot_hash") or record.get("snapshot_sha256"),
                "quality_weight": (
                    {"primary": Decimal("1.0"), "secondary": Decimal("0.75"), "unknown": Decimal("0.5")}.get(quality.get("source_type"), Decimal("0.5"))
                    * {"fresh": Decimal("1.0"), "aging": Decimal("0.75"), "unknown": Decimal("0.5")}.get(quality.get("freshness"), Decimal("0.5"))
                ),
                "claim": str(claim["claim"]).strip(),
            })
    return by_factor


def score_opportunity(records):
    """Return deterministic 0..100 desirability score with unknowns kept explicit."""
    inputs = _factor_entries(records)
    factors, known_weight, weighted_sum, conflicts = {}, Decimal("0"), Decimal("0"), []
    for key, weight in FACTOR_WEIGHTS.items():
        entries = inputs[key]
        if not entries:
            factors[key] = {"status": "UNKNOWN / NEEDS_EVIDENCE", "weight": str(weight), "value": None, "evidence": []}
            continue
        # Independent sources are averaged once each; repeated passages from one
        # source identity have already been collapsed by the Research boundary.
        value = sum((entry["value"] * entry["quality_weight"] for entry in entries), Decimal("0")) / sum((entry["quality_weight"] for entry in entries), Decimal("0"))
        factors[key] = {
            "status": "EVIDENCE_BACKED", "weight": str(weight),
            "value": str(value.quantize(Decimal("0.01"))),
            "evidence": [{k: str(v) if isinstance(v, Decimal) else v for k, v in entry.items()} for entry in entries],
        }
        known_weight += weight
        weighted_sum += weight * value
        if len(entries) > 1 and max(entry["value"] for entry in entries) - min(entry["value"] for entry in entries) >= Decimal("40"):
            conflicts.append(key)
    score = (weighted_sum / known_weight).quantize(Decimal("0.01")) if known_weight else None
    return {
        "score": float(score) if score is not None else None,
        "rationale": "Weighted mean of evidence-backed factors only; unknown factors are excluded and disclosed.",
        "status": "scored" if score is not None else "needs_evidence",
        "rubric": {
            "id": RUBRIC_VERSION, "version": RUBRIC_VERSION,
            "evidence_ids": sorted({item.get("evidence_id") for values in inputs.values() for item in values if item.get("evidence_id")}),
            "weights": {key: str(value) for key, value in FACTOR_WEIGHTS.items()},
            "inputs": factors,
            "evidence_references": sorted({
                canonical_digest({"source_id": item["source_id"], "evidence_id": item["evidence_id"], "snapshot_digest": item["snapshot_digest"]})
                for values in inputs.values() for item in values
            }),
            "calculation": "sum(weight*mean(independent source ratings))/sum(weights for known factors)",
            "known_weight": str(known_weight), "coverage": float(known_weight),
            "unknown_factors": [key for key, value in factors.items() if value["status"] != "EVIDENCE_BACKED"],
            "conflicts": conflicts, "assumptions": ["Factor ratings are 0..100 desirability assessments supported by listed source claims."],
            "uncertainty": "Unknown factors remain unknown; source disagreement is recorded as conflict.",
            "evidence_digest": canonical_digest([record.get("snapshot_hash") or record.get("snapshot_sha256") for record in records or []]),
        },
    }


def validate_opportunity(opportunity, records, research_attempts=1):
    rubric = (opportunity or {}).get("rubric") or {}
    inputs = rubric.get("inputs") or {}
    required = (
        "market_demand", "willingness_to_pay", "expected_revenue_potential",
        "expected_profit_potential", "build_cost_efficiency", "operating_cost_efficiency",
        "execution_feasibility", "legal_safety", "security_safety",
    )
    missing = [key for key in required if (inputs.get(key) or {}).get("status") != "EVIDENCE_BACKED"]
    usable_records = [item for item in records or [] if ((item.get("provenance") or {}).get("source_quality") or {}).get("freshness") != "stale"]
    unique_sources = {str(item.get("source_identity") or item.get("source") or "") for item in usable_records}
    unique_sources.discard("")
    if len(unique_sources) < 2:
        missing.append("independent_source_coverage")
    conflicts = list(rubric.get("conflicts") or [])
    score = opportunity.get("score") if opportunity else None
    if conflicts:
        outcome = "RESEARCH_AGAIN"
        reason = "Independent source assessments materially conflict."
    elif missing:
        outcome = "NEEDS_MORE_EVIDENCE" if int(research_attempts or 1) < 2 else "BLOCKED"
        reason = "Required commercial assumptions lack independent evidence." if outcome != "BLOCKED" else "Bounded research attempts exhausted with material evidence gaps."
    elif score is not None and float(score) < 45:
        outcome = "REJECTED"
        reason = "Evidence-backed opportunity score is below the versioned minimum threshold."
    else:
        outcome = "VALIDATED"
        reason = "Required commercial factors have independent evidence and the opportunity clears the cheap-validation threshold."
    return {
        "outcome": outcome, "policy_version": VALIDATION_POLICY_VERSION,
        "criteria": {"minimum_unique_sources": 2, "required_factors": list(required), "minimum_score": 45,
                     "score": score, "unique_source_count": len(unique_sources), "known_factor_coverage": rubric.get("coverage", 0)},
        "evidence_references": sorted({str(item.get("evidence_id")) for item in records or [] if item.get("evidence_id")}),
        "evidence_digest": rubric.get("evidence_digest"), "score_rubric_version": rubric.get("version"),
        "missing_factors": missing, "conflicts": conflicts, "reason": reason,
        "assumptions": ["Validation is a bounded, low-cost desk validation; it does not claim collected revenue or paying customers."],
    }
