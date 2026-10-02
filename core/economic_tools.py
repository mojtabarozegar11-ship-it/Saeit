"""Concrete economic tools for the single master agent.

These handlers create verifiable project artifacts. They never claim revenue
without external settlement evidence.
"""
import json
from pathlib import Path
from django.conf import settings
from django.utils import timezone

WORKDIR = Path(settings.BASE_DIR) / "var" / "economic_master"

def _write(name, payload):
    WORKDIR.mkdir(parents=True, exist_ok=True)
    path = WORKDIR / name
    payload = dict(payload)
    payload["updated_at"] = timezone.now().isoformat()
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "action_performed": f"created_or_updated:{name}",
        "verified_effect": path.exists() and path.stat().st_size > 20,
        "evidence": {"artifact": str(path), "bytes": str(path.stat().st_size)},
        "artifact": payload,
    }

def market_research(data):
    return _write("01_market_research.json", {
        "goal": data.get("objective", ""),
        "decision": "Build a sellable digital service from existing site capabilities.",
        "validation_needed": ["named buyer segment", "pain evidence", "competitor evidence", "reachable channel"],
        "status": "research_artifact_created",
    })

def opportunity_score(data):
    return _write("02_opportunity_score.json", {
        "criteria": ["time_to_market", "startup_cost", "margin", "automation", "demand_evidence"],
        "rule": "Do not advance an offer without evidence for buyer, pain and channel.",
        "status": "scoring_gate_created",
    })

def offer_design(data):
    return _write("03_offer_design.json", {
        "offer": "AI Workflow Automation Audit",
        "deliverables": ["workflow inventory", "automation opportunities", "priority roadmap", "implementation estimate"],
        "status": "offer_spec_created",
    })

def mvp_build(data):
    return _write("04_mvp.json", {
        "product": "AI Workflow Automation Audit",
        "delivery": ["intake", "audit", "findings", "roadmap"],
        "quality_gate": "must be reviewed before external publication",
        "status": "mvp_package_created",
    })

def growth_experiment(data):
    return _write("05_growth.json", {
        "experiment": "manual permission-respecting outreach to validated prospects",
        "metrics": ["qualified_leads", "replies", "conversions"],
        "status": "experiment_plan_created_not_claimed_executed",
    })

def revenue_verify(data):
    return _write("06_revenue_verify.json", {
        "verified_revenue": False,
        "reason": "No reconciled external settlement evidence supplied.",
        "status": "verification_gate_enforced",
    })

def profit_optimize(data):
    return _write("07_profit_optimize.json", {
        "rule": "Optimize only from verified revenue and measured direct costs.",
        "status": "profit_gate_created",
    })
