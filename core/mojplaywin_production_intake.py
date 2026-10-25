"""Read-only production brief intake for MojPlayWin's existing on-site cards.

Website activity describes an opportunity, not verified customer demand.
No order, research task, payment, approval, or public product is created here.
"""
from __future__ import annotations

import hashlib

# Reviewed digital deliverables, in the exact order of the three existing
# venture cards. Priority (1..5) is an editorial feasibility hypothesis only.
RECIPES = {
    "agriculture": (
        ("Farm Cost & Margin Planner", "xlsx+pdf", "Scenario workbook and instructions", 5),
        ("Crop & Irrigation Decision Workbook", "xlsx+pdf", "Editable water budget with assumptions", 4),
        ("Harvest-to-Market Readiness Kit", "pdf+xlsx", "Packaging, storage and channel checklists", 4)),
    "cafe-restaurant": (
        ("Cafe Concept & Guest Journey Kit", "pdf+docx", "Concept canvas and service templates", 4),
        ("Menu Costing & Stock Calculator", "xlsx+pdf", "Ingredient cost model with test data", 5),
        ("Hospitality Digital Experience Audit", "pdf+xlsx", "Booking and menu journey checklist", 4)),
    "fuel-station": (
        ("Roadside-Service Feasibility Planner", "xlsx+pdf", "Illustrative feasibility scenarios", 3),
        ("Convenience Retail Inventory Workbook", "xlsx+pdf", "Stock and reorder templates", 4),
        ("Mobility Technology Research Pack", "pdf+xlsx", "Source-linked assessment checklist", 3)),
    "jewelry-gold": (
        ("Jewelry Design Brief Templates", "pdf+docx", "Design and materials worksheets", 4),
        ("Jewelry Product Storytelling Toolkit", "docx+xlsx", "Care, origin and listing templates", 4),
        ("Jewelry E-commerce Listing Kit", "xlsx+pdf", "Digital catalogue fields and checklist", 4)),
    "carpets": (
        ("Carpet & Textile Provenance Guide", "pdf+docx", "Research documentation checklist", 3),
        ("Rug Collection Inventory Workbook", "xlsx+pdf", "Stock, dimensions and motif register", 4),
        ("Textile Online Catalogue Starter Pack", "xlsx+pdf", "Catalogue and product listing templates", 4)),
    "currency-crypto": (
        ("Currency Market Literacy Workbook", "pdf+xlsx", "Concepts, glossary, non-advisory exercises", 3),
        ("Blockchain Concepts Learning Pack", "pdf+docx", "Educational lessons and self-assessment", 3),
        ("Market Research Risk Checklist", "pdf+xlsx", "Source and uncertainty worksheet; no investment advice", 4)),
    "ecommerce": (
        ("Accessible Storefront Audit Toolkit", "pdf+xlsx", "Accessibility and catalogue checklist", 5),
        ("Digital Product Delivery Test Kit", "pdf+xlsx", "Entitlement and download acceptance tests", 5),
        ("Post-Purchase Customer Journey Kit", "docx+xlsx", "Order communications and support templates", 5)),
    "hospitality": (
        ("Guest Service SOP Starter Pack", "docx+pdf", "Editable service procedures", 4),
        ("Guest Communication Template Library", "docx+pdf", "Arrival and feedback message templates", 4),
        ("Hospitality Operations Tracker", "xlsx+pdf", "Requests and shifts workbook with example data", 4)),
}
RELEASE_CHECKS = (
    "Validate original sources, owner identity and content rights",
    "Verify customer need independently; a site card is not purchase demand",
    "Create a functional original deliverable and documented limitations",
    "Test actual file, compatibility, calculations and accessibility",
    "Independently verify price, checkout, refunds and automatic delivery",
)


class IntakeSourceMismatch(ValueError):
    """Stop rather than create speculative orders from unexpected site cards."""


def propose_production_orders(ventures):
    """Create deterministic, non-persistent internal production proposals."""
    if len(ventures) != len(RECIPES) or {v["slug"] for v in ventures} != set(RECIPES):
        raise IntakeSourceMismatch("Venture cards differ from reviewed recipe catalog")
    proposals = []
    for venture in ventures:
        slug = venture["slug"]
        recipes = RECIPES[slug]
        cards = venture["cards"]
        if len(cards) != len(recipes):
            raise IntakeSourceMismatch("Unexpected card count in " + slug)
        for index, (card, recipe) in enumerate(zip(cards, recipes), start=1):
            if not isinstance(card, (tuple, list)) or len(card) != 2 or not all(isinstance(x, str) and x.strip() for x in card):
                raise IntakeSourceMismatch("Invalid venture card in " + slug)
            title, format_name, deliverable, priority = recipe
            identifier = hashlib.sha256(f"mojplaywin.com/{slug}/{index}".encode()).hexdigest()[:12].upper()
            proposals.append({
                "id": "MPW-PO-" + identifier,
                "type": "internal_production_proposal",
                "source_site": "mojplaywin.com",
                "source_url": venture["url"],
                "source_card_title": card[0],
                "source_card_description": card[1],
                "source_card_number": index,
                "source_venture": slug,
                "product_title": title,
                "format": format_name,
                "deliverable": deliverable,
                "priority_hypothesis": priority,
                "customer_demand_verified": False,
                "owner_provenance_verified": False,
                "rights_verified": False,
                "quality_verified": False,
                "status": "proposed_for_review",
                "customer_order": False,
                "store_publication_allowed": False,
                "checkout_enabled": False,
                "price": None,
                "release_checks": list(RELEASE_CHECKS),
            })
    if len({item["id"] for item in proposals}) != len(proposals):
        raise IntakeSourceMismatch("Duplicate card identity")
    return sorted(proposals, key=lambda item: (-item["priority_hypothesis"], item["id"]))


def other_activity_signals(sections, features):
    """Track wider section and feature cards as needs, not fake orders."""
    signals = []
    for key, section in sections.items():
        if not isinstance(section, (list, tuple)) or len(section) != 4:
            raise IntakeSourceMismatch("Unexpected section card schema")
        for pos, card in enumerate(section[3], start=1):
            if not isinstance(card, (tuple, list)) or len(card) != 2:
                raise IntakeSourceMismatch("Invalid section card")
            signals.append({"source": f"section:{key}:{pos}", "title": card[0], "description": card[1], "status": "needs_scoping", "customer_order": False})
    for pos, feature in enumerate(features, start=1):
        signals.append({"source": f"feature:{pos}", "title": feature["title"], "description": feature["text"], "status": "needs_scoping", "customer_order": False})
    return signals


def build_intake(ventures, sections, features):
    proposals = propose_production_orders(ventures)
    signals = other_activity_signals(sections, features)
    return {
        "schema_version": 1,
        "site": "mojplaywin.com",
        "mode": "read_only_proposals",
        "proposals_total": len(proposals),
        "other_signals_total": len(signals),
        "customer_orders_created": 0,
        "factory_tasks_created": 0,
        "published_products_created": 0,
        "production_proposals": proposals,
        "other_activity_signals": signals,
    }
