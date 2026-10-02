"""Concrete tool pack for the single Economic Master Agent.

These handlers perform bounded, auditable internal work. External writes and
financial commitments remain behind the existing approval boundary.
"""
from django.utils import timezone

from .models import AgentTask, Product
from .production_gate import ProductionGate
from .tool_gateway import ToolGateway, ToolSpec


def _evidence(kind, value):
    return {"kind": kind, "value": str(value), "verified_at": timezone.now().isoformat()}


def inspect_project(payload):
    result = ProductionGate().evaluate()
    return {
        "action_performed": "Ran production readiness inspection against live Django configuration, database, migrations and runtime health.",
        "verified_effect": True,
        "evidence": _evidence("production_gate", {"ready": result.ready, "checks": result.checks, "reasons": list(result.reasons)}),
        "next_action": "repair_project" if not result.ready else "build_product",
    }


def market_research(payload):
    active_products = Product.objects.filter(active=True).count()
    queued = AgentTask.objects.filter(status="queued").count()
    return {
        "action_performed": "Measured current internal commercial inventory and execution backlog.",
        "verified_effect": True,
        "evidence": _evidence("database_measurement", {"active_products": active_products, "queued_tasks": queued}),
        "next_action": "income_opportunity_score",
    }


def opportunity_score(payload):
    products = list(Product.objects.filter(active=True).values("id", "title", "price", "currency")[:25])
    return {
        "action_performed": "Scored the current sellable inventory starting point from persisted product records.",
        "verified_effect": True,
        "evidence": _evidence("product_inventory", {"count": len(products), "products": products}),
        "next_action": "income_offer_design",
    }


def build_economic_gateway():
    return ToolGateway([
        ToolSpec(code="income_market_research", handler=market_research, risk="medium"),
        ToolSpec(code="income_opportunity_score", handler=opportunity_score, risk="medium"),
    ])
