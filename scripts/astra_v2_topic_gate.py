#!/usr/bin/env python3
"""Fail-closed, private-only research triage for Astra V2's external prototype inbox.

The report is PROVISIONAL: source URLs and claimed scores do not prove buyer
demand or authorize commercial production, public release, or payment.
No network access, site/production database access, or credential use.
"""
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MARKER = ".enable-topic-research-gate"
DOSSIERS = "topic-research-dossiers.json"
MAX_BYTES = 5_000_000


def enabled(root):
    p = Path(root) / MARKER
    if p.is_symlink():
        raise ValueError("unsafe topic gate marker")
    if not p.exists():
        return False
    if not p.is_file() or p.read_text(encoding="utf-8").strip() != "private_only":
        raise ValueError("unsafe topic gate marker")
    return True


def verdicts(root):
    """Recompute evidence/score checks from the raw local dossier, never a supplied verdict."""
    p = Path(root) / DOSSIERS
    if p.is_symlink():
        return {}, "UNSAFE_DOSSIER"
    if not p.is_file():
        return {}, "NO_DOSSIER"
    try:
        if p.stat().st_size > MAX_BYTES:
            return {}, "OVERSIZED_DOSSIER"
        data = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or set(data) != {"candidates", "snapshots"}:
            return {}, "INVALID_DOSSIER"
        script = ROOT / "astra_opportunity_selector.py"
        if script.is_symlink() or not script.is_file():
            return {}, "SELECTOR_MISSING"
        spec = importlib.util.spec_from_file_location("astra_topic_quality_selector", str(script))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        result = mod.rank_opportunities(
            data["candidates"], data["snapshots"], datetime.now(timezone.utc))
        # REVIEW_REQUIRED allows *only* an isolated technical prototype to be
        # considered for the approved builder. It NEVER authorizes real goods,
        # commercial release, a web-site write, or claims of verified evidence.
        return {row["opportunity_key"]: row for row in result["candidates"]}, "PROVISIONAL"
    except (OSError, ValueError, TypeError, KeyError, UnicodeDecodeError,
            json.JSONDecodeError):
        return {}, "INVALID_DOSSIER"


def private_prototype_eligible(row):
    if not isinstance(row, dict):
        return False
    claims = row.get("claim_source_domains_preliminary")
    return (
        row.get("status") == "REVIEW_REQUIRED"
        and type(row.get("priority_score")) in (int, float)
        and row["priority_score"] >= 60
        and type(row.get("distinct_source_domains_preliminary")) is int
        and row["distinct_source_domains_preliminary"] >= 3
        and isinstance(claims, dict)
        and all(type(claims.get(name)) is int and claims[name] >= 1
                for name in ("problem", "willingness_to_pay", "comparison", "feasibility"))
        and row.get("evidence_verified_independently") is False
        and row.get("build_authorized") is False
        and row.get("publish_authorized") is False
        and row.get("payment_authorized") is False
    )
