"""Idempotent, opt-in creation of internal briefs from verified main-site cards.

Never writes customer Order, Product, AgentTask, payments or factory state.
"""
from django.db import transaction

from .mojplaywin_production_intake import build_intake
from .mojplaywin_production_models import (
    MojPlayWinManufacturingOrder,
    MojPlayWinOpportunitySignal,
)
from .mojplaywin_views import FEATURES, SECTIONS, VENTURES


def prepare_main_site_cards():
    """Produce reviewed source snapshots before any DB operation."""
    intake = build_intake(VENTURES, SECTIONS, FEATURES)
    signals = []
    for proposal in intake["production_proposals"]:
        signals.append({
            "source_key": "venture:%s:%s" % (proposal["source_venture"], proposal["source_card_number"]),
            "source_kind": "venture",
            "source_path": proposal["source_url"],
            "card_title": proposal["source_card_title"],
            "card_description": proposal["source_card_description"],
        })
    for extra in intake["other_activity_signals"]:
        kind = extra["source"].split(":", 1)[0]
        if kind not in ("section", "feature"):
            raise ValueError("Unexpected activity signal kind")
        signals.append({
            "source_key": extra["source"],
            "source_kind": kind,
            "source_path": "",
            "card_title": extra["title"],
            "card_description": extra["description"],
        })
    if len({row["source_key"] for row in signals}) != len(signals):
        raise ValueError("Duplicate activity source keys")
    return intake, signals


def sync_main_site_production_bank():
    """Persist *internal proposals only*; don't update manually reviewed work."""
    intake, source_rows = prepare_main_site_cards()
    source_objects = {}
    result = {
        "site": "mojplaywin.com",
        "mode": "persist_internal_proposals",
        "signals_total": len(source_rows),
        "briefs_total": len(intake["production_proposals"]),
        "signals_created": 0,
        "briefs_created": 0,
        "existing_signals_kept": 0,
        "existing_briefs_kept": 0,
        "public_products_created": 0,
        "customer_orders_created": 0,
        "factory_tasks_created": 0,
    }
    with transaction.atomic():
        for row in source_rows:
            signal, was_created = MojPlayWinOpportunitySignal.objects.get_or_create(
                source_key=row["source_key"],
                defaults=row,
            )
            if signal.source_site != MojPlayWinOpportunitySignal.SITE:
                raise ValueError("Foreign-site source key collision")
            source_objects[row["source_key"]] = signal
            result["signals_created" if was_created else "existing_signals_kept"] += 1

        for proposal in intake["production_proposals"]:
            key = "venture:%s:%s" % (proposal["source_venture"], proposal["source_card_number"])
            signal = source_objects[key]
            brief, was_created = MojPlayWinManufacturingOrder.objects.get_or_create(
                proposal_id=proposal["id"],
                defaults={
                    "signal": signal,
                    "product_title": proposal["product_title"],
                    "file_format": proposal["format"],
                    "deliverable": proposal["deliverable"],
                    "priority_hypothesis": proposal["priority_hypothesis"],
                },
            )
            if brief.signal_id != signal.pk:
                raise ValueError("Manufacturing brief proposal/source mismatch")
            result["briefs_created" if was_created else "existing_briefs_kept"] += 1
    return result
