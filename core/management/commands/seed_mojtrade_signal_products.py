"""Seed the MojTrade signal SKUs from the canonical catalog.

The command is idempotent and creates inactive products by default. Activation
requires an explicit release flag so a source change cannot silently publish a
paid product before checkout, settlement and delivery checks pass.
"""
from __future__ import annotations

import json
import os
from decimal import Decimal
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.models import Product


CATALOG = (
    Path(__file__).resolve().parents[3]
    / "runtime"
    / "mojtrade_signal_catalog_v1.json"
)
RELEASE_FLAG = "MOJ_SIGNAL_RELEASE_APPROVED"


def load_catalog(path: Path = CATALOG) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CommandError("SIGNAL_CATALOG_UNREADABLE") from exc
    if (
        not isinstance(data, dict)
        or data.get("schema") != "mojtaba.bot.ai.signal-catalog.v1"
        or data.get("canonical_bot_id") != "mojtaba.bot.ai"
    ):
        raise CommandError("SIGNAL_CATALOG_INVALID")
    tiers = data.get("tiers")
    if (
        not isinstance(tiers, list)
        or len(tiers) != 3
        or [tier.get("price_trx") for tier in tiers] != [5, 10, 15]
        or any(
            tier.get("validity_days") != 15
            or tier.get("max_verified_signals") != 10
            for tier in tiers
        )
        for tier in tiers
    ):
        raise CommandError("SIGNAL_CATALOG_TIERS_INVALID")
    return data


class Command(BaseCommand):
    help = "Create or update inactive MojTrade signal products from the canonical catalog."

    def add_arguments(self, parser):
        parser.add_argument(
            "--activate",
            action="store_true",
            help="Activate products only when MOJ_SIGNAL_RELEASE_APPROVED=1.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        catalog = load_catalog()
        activating = bool(options["activate"])
        if activating and os.environ.get(RELEASE_FLAG) != "1":
            raise CommandError("SIGNAL_RELEASE_APPROVAL_FLAG_REQUIRED")
        active = activating
        created = 0
        updated = 0
        for tier in catalog["tiers"]:
            code = str(tier["code"])
            title = f"MojTrade {code}"
            product, was_created = Product.objects.get_or_create(
                title=title,
                product_type="signal",
                defaults={
                    "price": Decimal(str(tier["price_trx"])),
                    "currency": "TRX",
                    "active": active,
                    "metadata": {},
                },
            )
            metadata = {
                **(product.metadata or {}),
                "canonical_bot_id": catalog["canonical_bot_id"],
                "catalog_schema": catalog["schema"],
                "signal_market_scope": catalog["market_scope"],
                "validity_days": tier["validity_days"],
                "max_verified_signals": tier["max_verified_signals"],
                "delivery_primary": catalog["delivery"]["primary"],
                "delivery_backup": catalog["delivery"]["backup"],
                "receiver": catalog["payment"]["receiver"],
                "commercial_status": "release_approved" if active else "catalog_seeded_inactive",
            }
            product.price = Decimal(str(tier["price_trx"]))
            product.currency = "TRX"
            product.active = active
            product.metadata = metadata
            product.save(update_fields=["price", "currency", "active", "metadata", "updated_at"])
            created += int(was_created)
            updated += int(not was_created)
        self.stdout.write(
            self.style.SUCCESS(
                f"SIGNAL_PRODUCTS_READY created={created} updated={updated} active={int(active)}"
            )
        )
