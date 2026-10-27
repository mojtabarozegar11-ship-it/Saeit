"""Concrete tool pack for the single Economic Master Agent.

These handlers perform bounded, auditable internal work. External writes and
financial commitments remain behind the existing approval boundary.
"""
import os
import importlib.util
from pathlib import Path

from django.utils import timezone
from .factory_native_review_gateway import inspect_family
from .factory_f41_gateway import build_verified_order

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



def offer_design(payload):
    inactive = Product.objects.filter(active=False).order_by("id").first()
    if inactive:
        inactive.metadata = {
            **(inactive.metadata or {}),
            "commercial_status": "offer_designed",
            "offer_designed_at": timezone.now().isoformat(),
            "value_proposition": "Deliver a concrete, measurable outcome with transparent scope and evidence.",
        }
        inactive.save(update_fields=["metadata", "updated_at"])
        product = inactive
        created = False
    else:
        product = Product.objects.create(
            title="Digital Project & Automation Audit",
            product_type="service",
            price=0,
            currency="USD",
            active=False,
            metadata={
                "commercial_status": "offer_designed",
                "offer_designed_at": timezone.now().isoformat(),
                "value_proposition": "Audit a digital workflow and return prioritized, evidence-backed improvements.",
                "pricing_status": "requires_market_evidence",
            },
        )
        created = True
    return {
        "action_performed": f"{'Created' if created else 'Updated'} product offer {product.pk}: {product.title}.",
        "verified_effect": True,
        "evidence": _evidence("product_record", {"id": product.pk, "status": product.metadata.get("commercial_status")}),
        "next_action": "income_mvp_build",
    }


def mvp_build(payload):
    product = Product.objects.filter(metadata__commercial_status="offer_designed").order_by("id").first()
    if not product:
        raise ValueError("No designed offer exists; run income_offer_design first.")
    product.metadata = {
        **(product.metadata or {}),
        "commercial_status": "mvp_built",
        "mvp_built_at": timezone.now().isoformat(),
        "deliverables": [
            "current-state audit",
            "prioritized improvement plan",
            "measurable acceptance criteria",
            "implementation-ready action list",
        ],
        "quality_gate": "pending",
    }
    product.save(update_fields=["metadata", "updated_at"])
    return {
        "action_performed": f"Built persisted MVP specification for product {product.pk}: {product.title}.",
        "verified_effect": True,
        "evidence": _evidence("mvp_record", {"id": product.pk, "deliverables": product.metadata["deliverables"]}),
        "next_action": "income_growth_experiment",
    }


def growth_experiment(payload):
    product = Product.objects.filter(metadata__commercial_status="mvp_built").order_by("id").first()
    if not product:
        raise ValueError("No built MVP exists; run income_mvp_build first.")
    product.metadata = {
        **(product.metadata or {}),
        "commercial_status": "growth_ready",
        "growth_experiment": {
            "hypothesis": "A clearly scoped audit with measurable acceptance criteria is more actionable than a generic consultation.",
            "metric": "qualified_lead_to_purchase_conversion",
            "status": "ready_for_approved_external_test",
        },
        "growth_prepared_at": timezone.now().isoformat(),
    }
    product.save(update_fields=["metadata", "updated_at"])
    return {
        "action_performed": f"Prepared measurable growth experiment for product {product.pk} without performing an unapproved external write.",
        "verified_effect": True,
        "evidence": _evidence("growth_experiment", product.metadata["growth_experiment"]),
        "next_action": "income_revenue_verify",
    }


def revenue_verify(payload):
    # Never invent revenue: only persisted payment/ledger evidence may support it.
    from .models import LedgerEntry
    settled = list(LedgerEntry.objects.filter(entry_type__in=("settlement", "payment")).values(
        "id", "amount", "currency", "reference"
    )[:100])
    total = sum((item["amount"] for item in settled), 0)
    return {
        "action_performed": "Reconciled persisted ledger payment/settlement evidence; no unevidenced revenue was counted.",
        "verified_effect": True,
        "evidence": _evidence("ledger_reconciliation", {"entries": len(settled), "total": total}),
        "verified_revenue": str(total),
        "next_action": "income_profit_optimize",
    }


def profit_optimize(payload):
    active = list(Product.objects.filter(active=True).values("id", "title", "price", "currency")[:100])
    return {
        "action_performed": "Measured active sellable catalog for the next allocation decision without fabricating margin data.",
        "verified_effect": True,
        "evidence": _evidence("profit_baseline", {"active_products": len(active), "products": active}),
        "next_action": "income_market_research",
    }


def master_self_improvement(payload):
    """Build privately verified candidates from the allowlisted repair engine."""
    if os.getenv("MOJ_FACTORY_LOCAL_MODE") != "1":
        raise ValueError("MASTER_SELF_IMPROVEMENT_PRIVATE_RUNTIME_ONLY")
    repo = Path(__file__).resolve().parents[1]
    engine_path = repo / "scripts" / "factory_code_self_upgrade.py"
    if engine_path.is_symlink() or not engine_path.is_file():
        raise ValueError("MASTER_SELF_IMPROVEMENT_ENGINE_MISSING")
    spec = importlib.util.spec_from_file_location("master_self_upgrade_engine", engine_path)
    if spec is None or spec.loader is None:
        raise ValueError("MASTER_SELF_IMPROVEMENT_ENGINE_LOAD_FAILED")
    engine = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(engine)
    output = Path.home() / "factory-runtime" / "private" / "master-agent" / "code-upgrade"
    report = engine.generate(repo, output)
    verified = (
        report.get("unresolved_known_security_regressions") == 0
        and report.get("validated_repair_rule_coverage", 0)
        == report.get("candidate_count", 0) + report.get("preexisting_verified_repairs", 0)
    )
    return {
        "action_performed": "Ran the bounded private code-upgrade engine and wrote its candidate/evidence dossier.",
        "verified_effect": verified,
        "evidence": _evidence("private_self_upgrade_dossier", {
            "candidate_count": report.get("candidate_count"),
            "measured_improvements": report.get("candidates_with_measured_improvement"),
            "verified_existing_repairs": report.get("preexisting_verified_repairs"),
            "production_promotions": report.get("production_code_promotions"),
            "whole_code_autonomous_evolution_complete": report.get("whole_code_autonomous_evolution_complete"),
            "dossier": str(output / "evolution-proof.json"),
        }),
        "production_promotion": False,
        "next_action": "income_market_research",
    }


def factory_native_review(payload):
    # This executor is intentionally *private VPS-only*. Never accept a
    # caller-supplied root, production website path, or output destination.
    if os.getenv("MOJ_FACTORY_LOCAL_MODE") != "1":
        raise ValueError("NATIVE_MASTER_PRIVATE_VPS_ONLY")
    root = Path.home() / "factory-runtime" / "private" / "autonomous-product-cycle"
    return inspect_family(root, payload)


def build_economic_gateway():
    return ToolGateway([
        ToolSpec(code="factory_native_review",handler=factory_native_review,risk="low"),
        ToolSpec(code="factory_f41_private_build",handler=build_verified_order,risk="low"),
        ToolSpec(code="income_market_research", handler=market_research, risk="medium"),
        ToolSpec(code="income_opportunity_score", handler=opportunity_score, risk="medium"),
        ToolSpec(code="income_offer_design", handler=offer_design, risk="medium"),
        ToolSpec(code="income_mvp_build", handler=mvp_build, risk="medium"),
        ToolSpec(code="income_growth_experiment", handler=growth_experiment, risk="medium"),
        ToolSpec(code="income_revenue_verify", handler=revenue_verify, risk="medium"),
        ToolSpec(code="income_profit_optimize", handler=profit_optimize, risk="medium"),
        ToolSpec(code="master_self_improvement", handler=master_self_improvement, risk="medium"),
    ])
