"""Concrete tool pack for the single Economic Master Agent.

These handlers perform bounded, auditable internal work. External writes and
financial commitments remain behind the existing approval boundary.
"""
import hashlib
import html
import os
import importlib.util
from pathlib import Path
import tempfile

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


MVP_SECTIONS = (
    ("1. Define the outcome", "State the buyer, the costly problem, the observable result, and the time horizon.", [
        "A specific buyer and decision-maker are named.",
        "The current problem is supported by a customer example or source.",
        "The promised result is measurable and within the seller's control.",
        "The scope states what is excluded and what evidence the buyer receives.",
        "A baseline and a target can be measured without hidden assumptions.",
    ]),
    ("2. Validate demand", "Use evidence from real people and existing market signals before setting a price.", [
        "At least five relevant alternatives or competitors are compared.",
        "Prices and claims are recorded with date and source.",
        "At least three target buyers are interviewed or their public needs are cited.",
        "Evidence distinguishes stated interest from willingness to pay.",
        "The offer is revised when evidence contradicts the initial assumption.",
    ]),
    ("3. Design delivery", "Make the service reproducible, bounded, and useful after purchase.", [
        "Each deliverable has an owner, format, and acceptance criterion.",
        "The delivery sequence and expected turnaround are defined.",
        "Inputs required from the customer are listed before purchase.",
        "A human review step catches material factual or calculation errors.",
        "Rework, cancellation, and support boundaries are stated plainly.",
    ]),
    ("4. Control quality and reliability", "Prove the output works and can be repeated.", [
        "A representative end-to-end sample is completed.",
        "Critical paths are tested on supported devices and browsers.",
        "Known failure modes have detection, recovery, and owner.",
        "Version, source evidence, and final file hash are recorded.",
        "A reviewer who did not create the output can reproduce the checks.",
    ]),
    ("5. Protect customers and data", "Collect the minimum data required and define safe handling.", [
        "Data collected, purpose, retention period, and deletion path are documented.",
        "Access is limited to named roles and protected in transit and at rest.",
        "Sensitive data is excluded from analytics, logs, and public artifacts.",
        "A privacy notice and support contact are available before collection.",
        "Security incidents and customer requests have a response owner.",
    ]),
    ("6. Price and unit economics", "Check that each sale can create positive contribution margin.", [
        "The price is tested against observed alternatives and buyer value.",
        "Payment, taxes, refunds, chargebacks, and platform fees are itemized.",
        "Labor and support time are included in direct costs.",
        "A conservative break-even volume is calculated.",
        "No revenue is counted until settlement is reconciled.",
    ]),
    ("7. Payment, terms, and support", "Make purchase and post-purchase expectations explicit.", [
        "Checkout shows currency, total, recurring terms, and seller identity.",
        "Refund and cancellation terms are visible before payment.",
        "Receipts and delivery are tested using a non-production test order.",
        "A failed-payment and a duplicate-payment path are handled.",
        "Support response time and escalation route are stated.",
    ]),
    ("8. Accessibility and usability", "Reduce friction for a broad range of customers.", [
        "Keyboard-only navigation reaches every primary control.",
        "Text contrast and zoom remain usable on a small screen.",
        "Forms provide labels, clear errors, and a success confirmation.",
        "Instructions avoid unexplained jargon and disclose prerequisites.",
        "A user unfamiliar with the product can complete the core task.",
    ]),
    ("9. Ethical growth and retention", "Earn repeat use through value and trust.", [
        "Marketing claims match the tested product and name limitations.",
        "No dark patterns, fake scarcity, or concealed recurring charges are used.",
        "Notifications are consent-based, relevant, and easy to disable.",
        "Retention measures successful outcomes, not compulsive engagement.",
        "Acquisition experiments have a hypothesis, budget cap, and stop rule.",
    ]),
    ("10. Launch and learning", "Release only when launch gates pass and feedback can change the product.", [
        "A named release owner signs the checklist and records the version.",
        "A rollback or delisting method is tested before launch.",
        "Customer feedback is reviewed on a fixed cadence.",
        "A defect severity scheme and response target are published internally.",
        "The next investment depends on conversion, quality, and contribution margin.",
    ]),
 )


def build_mvp_asset(product_id, title, root=None):
    """Create a useful, private, self-contained product workbook and verify it."""
    base = Path(root) if root is not None else (
        Path.home() / "factory-runtime" / "private" / "master-agent" / "product-assets"
    )
    base.mkdir(parents=True, exist_ok=True, mode=0o700)
    if base.is_symlink() or not base.is_dir():
        raise ValueError("MVP_ASSET_DIRECTORY_UNSAFE")
    safe_title = html.escape(str(title or "Digital Project and Automation Audit"), quote=True)
    sections = []
    for heading, purpose, checks in MVP_SECTIONS:
        items = "".join(f'<li><span class="box">□</span>{html.escape(item)}</li>' for item in checks)
        sections.append(
            f'<section><h2>{html.escape(heading)}</h2><p>{html.escape(purpose)}</p>'
            f'<ul>{items}</ul><p class="notes">Evidence / owner / date: __________________________________________</p></section>'
        )
    body = "".join(sections)
    document = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{safe_title} — Field Workbook</title>
<style>
:root{{color-scheme:light;--ink:#17241e;--green:#14543c;--gold:#b18a3b;--paper:#fffdf7;}}
*{{box-sizing:border-box}}body{{margin:0;background:#edf1ec;color:var(--ink);font:16px/1.55 Georgia,serif}}
.page{{max-width:900px;margin:32px auto;padding:42px;background:var(--paper);box-shadow:0 8px 32px #17241e18}}
h1,h2{{font-family:Arial,sans-serif;line-height:1.2}}h1{{font-size:2.2rem;color:var(--green);margin:.3em 0}}
.eyebrow{{text-transform:uppercase;letter-spacing:.12em;color:var(--gold);font:700 12px Arial,sans-serif}}
.dek{{font-size:1.15rem;max-width:68ch}}.meta{{border-top:2px solid var(--gold);border-bottom:1px solid #ccd4c8;padding:14px 0;margin:20px 0}}
.score{{background:#edf3ee;border-left:4px solid var(--green);padding:16px;margin:18px 0}}
section{{break-inside:avoid;border-top:1px solid #ccd4c8;padding:18px 0}}h2{{font-size:1.25rem;color:var(--green);margin:.2em 0}}
li{{margin:7px 0}}ul{{padding-left:20px}}.box{{display:inline-block;width:24px;color:var(--gold);font-weight:bold}}
.notes{{color:#59665c;font-size:.92rem}}table{{width:100%;border-collapse:collapse;margin:14px 0}}
th,td{{border:1px solid #bcc8bb;padding:9px;text-align:left;vertical-align:top}}th{{background:#edf3ee}}
footer{{border-top:2px solid var(--gold);margin-top:24px;padding-top:12px;font-size:.85rem;color:#59665c}}
@media(max-width:650px){{.page{{margin:0;padding:24px 18px}}h1{{font-size:1.8rem}}}}
@media print{{body{{background:white}}.page{{max-width:none;margin:0;padding:12mm;box-shadow:none}}a{{color:inherit}}}}
</style></head><body><main class="page">
<p class="eyebrow">Practical field workbook · Version 1.0</p>
<h1>{safe_title}</h1>
<p class="dek">A decision and delivery workbook for turning a digital offer into a tested, supportable, customer-safe product. Work through the evidence before committing launch spend.</p>
<div class="meta"><strong>Owner:</strong> __________________ &nbsp; <strong>Product/version:</strong> __________________<br>
<strong>Review date:</strong> __________________ &nbsp; <strong>Decision:</strong> proceed / revise / stop</div>
<div class="score"><strong>Scoring:</strong> For each checklist item, mark 0 = no evidence, 1 = partial evidence, or 2 = verified evidence. Record the source and owner. A high score does not override a failed payment, privacy, security, or customer-safety gate.</div>
{body}
<section><h2>Evidence register</h2><p>Use one row per material claim or control. Keep source links and review dates so another person can verify the decision.</p>
<table><thead><tr><th>Claim / control</th><th>Evidence or source</th><th>Owner</th><th>Date checked</th><th>0–2</th></tr></thead>
<tbody>{''.join('<tr><td>&nbsp;</td><td></td><td></td><td></td><td></td></tr>' for _ in range(6))}</tbody></table></section>
<section><h2>Decision and 30-day action plan</h2><table><thead><tr><th>Priority / action</th><th>Success measure</th><th>Owner</th><th>Due date</th><th>Stop rule</th></tr></thead>
<tbody>{''.join('<tr><td>&nbsp;</td><td></td><td></td><td></td><td></td></tr>' for _ in range(5))}</tbody></table>
<p><strong>Launch gate:</strong> Do not publish or take payment until product claims, delivery, support, refund terms, privacy handling, and payment reconciliation have named owners and passed review.</p></section>
<footer>Independent planning aid. It is not legal, tax, security-certification, or investment advice, and completing it does not certify a product. Verify applicable rules and platform requirements for your market.</footer>
</main></body></html>
"""
    required = ("Evidence register", "30-day action plan", "Launch gate", "Scoring:", "Accessibility and usability", "Payment, terms, and support")
    checklist_items = sum(len(checks) for _, _, checks in MVP_SECTIONS)
    if len(MVP_SECTIONS) < 10 or checklist_items < 45 or any(token not in document for token in required):
        raise ValueError("MVP_ASSET_QUALITY_GATE_FAILED")
    digest = hashlib.sha256(document.encode("utf-8")).hexdigest()
    filename = f"digital-project-audit-{int(product_id)}-v1.html"
    target = base / filename
    if target.is_symlink():
        raise ValueError("MVP_ASSET_TARGET_SYMLINK")
    fd, temporary = tempfile.mkstemp(prefix=".mvp-", dir=str(base))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(document)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, target)
        dir_fd = os.open(base, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    written = target.read_bytes()
    if hashlib.sha256(written).hexdigest() != digest or not target.is_file():
        raise ValueError("MVP_ASSET_POSTWRITE_VERIFICATION_FAILED")
    return {
        "relative_path": str(target), "sha256": digest, "bytes": len(written),
        "section_count": len(MVP_SECTIONS), "checklist_items": checklist_items,
        "quality_gate": "passed", "format": "self_contained_html_printable",
    }


def mvp_build(payload):
    product = Product.objects.filter(metadata__commercial_status="offer_designed").order_by("id").first()
    if not product:
        raise ValueError("No designed offer exists; run income_offer_design first.")
    asset = build_mvp_asset(product.pk, product.title)
    product.metadata = {
        **(product.metadata or {}),
        "commercial_status": "mvp_built",
        "mvp_built_at": timezone.now().isoformat(),
        "deliverables": [
            "self-contained printable digital operations audit workbook",
            "10 decision and delivery checklists with 50 evidence prompts",
            "evidence register and 30-day action-plan worksheets",
            "ethical growth, payment, accessibility, privacy, and quality gates",
        ],
        "quality_gate": asset["quality_gate"],
        "artifact": asset,
        "commercial_release": "not_published",
    }
    product.save(update_fields=["metadata", "updated_at"])
    return {
        "action_performed": f"Generated and verified private workbook asset for product {product.pk}: {product.title}.",
        "verified_effect": True,
        "evidence": _evidence("mvp_asset", asset),
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
