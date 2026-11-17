"""Read-only, privacy-safe Moj Prop sales action queue from actual lead records.

Never sends email, charges a card, issues a quote, advances a lead, or creates
a settlement event. Only human-authenticated operations may review the queue.
No buyer names, addresses, notes or account data are serialized.
"""
import json
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Exists, OuterRef, Q
from django.utils import timezone

from core.models import MojPropDeliveryEvidence, MojPropOffer, MojPropRequest


ACTION_LABELS = {
    "urgent_unreviewed": "Review urgent new requests promptly; confirm scope and ability to deliver",
    "new_over_24h": "Triage unanswered new requests before they age out",
    "reviewing_without_draft": "Prepare a scoped draft after a real manual review",
    "draft_over_24h": "Check draft scope, deliverable rights, exclusions and price",
    "approved_not_issued": "Owner must separately authorize quote delivery",
    "issued_expires_soon": "Request a decision only through an approved contact route",
    "issued_already_expired": "Close or issue a separately reviewed new proposal version",
    "accepted_no_artifact": "Prepare the real private deliverable and verify its checksum",
    "prepared_not_dispatched": "Verify legal clearance and payment/credit before handoff",
    "sent_unacknowledged": "Check the independent delivery acknowledgement evidence",
    "digital_without_issued_quote": "Check catalog rights and stock/delivery before offering",
    "free_signals_awaiting_review": "Review one-off FREE educational example; never quote or send marketing without separate permission",
    "signals_without_issued_quote": "Route paid educational service via mojtaba.bot.ai only",
    "terminal_offer_internal_review": "Internal-only review of latest cancelled or expired offer; do not contact buyer without independent reauthorization",
    "starter30_unquoted_manual_review": "Review buyer-claimed ten-session Starter30 scope; unsent educational quote only after seller, buyer and law checks; never demand TRX",
}


def action_queue_snapshot(*, detail_limit=0):
    """Prioritized overlapping action categories, never fabricated conversion.

    Categories are independent and may include the same lead more than once.
    detail_limit=0 returns only totals; IDs require explicit operator option.
    """
    if type(detail_limit) is not int or not 0 <= detail_limit <= 25:
        raise ValueError("detail_limit must be 0..25")

    now = timezone.now()
    # Queue entries may become customer contact instructions. Do not surface
    # a lead without its documented consent or after its lifecycle closes.
    active = MojPropRequest.objects.filter(consent=True).exclude(
        status__in=("spam", "closed", "delivered")
    )
    valid_issued = MojPropOffer.objects.filter(
        lead_id=OuterRef("pk"),
        status__in=("issued", "accepted", "cancelled", "expired"),
        reviewed_at__isnull=False, issued_at__isnull=False,
    )
    any_draft = MojPropOffer.objects.filter(
        lead_id=OuterRef("pk"), status__in=("draft", "approved")
    )
    accepted = MojPropOffer.objects.filter(
        lead__consent=True,
        status="accepted", reviewed_at__isnull=False,
        issued_at__isnull=False, accepted_at__isnull=False,
    ).exclude(acceptance_reference="")
    # Terminal latest offers remain internally actionable; cancellation does
    # not authorize new outreach, even when the original lead once consented.
    newer_offer = MojPropOffer.objects.filter(
        lead_id=OuterRef("lead_id"), version__gt=OuterRef("version")
    )
    terminal_offer_review = MojPropOffer.objects.filter(
        status__in=("cancelled", "expired"),
        lead__consent=True,
        lead__status__in=("new", "reviewing", "offer_sent", "approved"),
    ).annotate(has_newer_offer=Exists(newer_offer)).filter(has_newer_offer=False)
    delivery_for_offer = MojPropDeliveryEvidence.objects.filter(
        offer_id=OuterRef("pk")
    )
    lead_needing_issued = active.annotate(
        has_issued=Exists(valid_issued)
    ).filter(has_issued=False)
    # These prefixes describe a buyer's *claimed* free research request.
    # This is only CRM triage, never a free paid entitlement or email opt-in.
    free_signals = active.filter(route="signals").filter(
        Q(notes__startswith="Requested free educational example:")
        | Q(notes__startswith="One-off FREE educational market-brief example request")
        | Q(notes__startswith="Please provide a FREE historical educational example")
    ).filter(status__in=("new", "reviewing"))
    # High-priority first-sale review queue: exactly the existing canonical
    # ten-session educational SKU, inferred only as a *buyer claim* from
    # notes the browser/lead controls, never a trustworthy payment/product ID.
    # Do not issue a second 30 TRX price or treat an already-offered request as
    # a new sale. SQL existence predicate avoids loading any private notes.
    starter30_unquoted = active.filter(
        route="blueprint", status__in=("new", "reviewing"),
        notes__startswith="Requested canonical product: MOJPROP-STARTER30 (",
    ).annotate(
        has_any_offer=Exists(MojPropOffer.objects.filter(lead_id=OuterRef("pk")))
    ).filter(has_any_offer=False)

    lists = (
        ("urgent_unreviewed", active.filter(
            status="new", horizon="urgent"
        ), "request_id"),
        ("new_over_24h", active.filter(
            status="new", created_at__lte=now - timedelta(days=1)
        ), "request_id"),
        ("reviewing_without_draft", active.filter(
            status="reviewing"
        ).exclude(pk__in=free_signals.values("pk")).annotate(
            has_draft=Exists(any_draft)
        ).filter(has_draft=False), "request_id"),
        ("draft_over_24h", MojPropOffer.objects.filter(
            status="draft", created_at__lte=now - timedelta(days=1)
        ).exclude(lead__status__in=("spam", "closed", "delivered")).filter(
            lead__consent=True
        ), "lead__request_id"),
        ("approved_not_issued", MojPropOffer.objects.filter(
            status="approved", reviewed_at__isnull=False,
            issued_at__isnull=True,
        ).exclude(lead__status__in=("spam", "closed", "delivered")).filter(
            lead__consent=True
        ), "lead__request_id"),
        ("issued_expires_soon", MojPropOffer.objects.filter(
            status="issued", issued_at__isnull=False,
            expires_at__gt=now,
            expires_at__lte=now + timedelta(days=1),
        ).exclude(lead__status__in=("spam", "closed", "delivered")).filter(
            lead__consent=True
        ), "lead__request_id"),
        ("issued_already_expired", MojPropOffer.objects.filter(
            status="issued", issued_at__isnull=False,
            expires_at__lte=now,
        ).exclude(lead__status__in=("spam", "closed", "delivered")).filter(
            lead__consent=True
        ), "lead__request_id"),
        ("accepted_no_artifact", accepted.exclude(
            lead__status__in=("spam", "closed", "delivered")
        ).annotate(
            has_delivery=Exists(delivery_for_offer)
        ).filter(has_delivery=False), "lead__request_id"),
        ("prepared_not_dispatched", MojPropDeliveryEvidence.objects.filter(
            status="prepared", offer__status="accepted", offer__lead__consent=True,
        ).exclude(
            offer__lead__status__in=("spam", "closed", "delivered")
        ), "offer__lead__request_id"),
        ("sent_unacknowledged", MojPropDeliveryEvidence.objects.filter(
            status="sent", handed_off_at__lte=now - timedelta(days=1),
            handoff_reference__gt="", clearance_reference__gt="",
            offer__status="accepted", offer__lead__consent=True,
        ).exclude(
            offer__lead__status__in=("spam", "closed", "delivered")
        ), "offer__lead__request_id"),
        ("terminal_offer_internal_review", terminal_offer_review, "lead__request_id"),
        ("starter30_unquoted_manual_review", starter30_unquoted, "request_id"),
        ("digital_without_issued_quote", lead_needing_issued.filter(
            route="digital", product_id__isnull=False,
        ), "request_id"),
        ("free_signals_awaiting_review", free_signals, "request_id"),
        ("signals_without_issued_quote", lead_needing_issued.filter(
            route="signals",
        ).exclude(pk__in=free_signals.values("pk")), "request_id"),
    )
    categories = []
    for name, query, ref_field in lists:
        entry = {
            "category": name,
            "count": query.count(),
            "next_action": ACTION_LABELS[name],
        }
        if name in ("terminal_offer_internal_review", "starter30_unquoted_manual_review"):
            entry["operator_only"] = True
            entry["customer_outreach_authorized"] = False
        if name == "starter30_unquoted_manual_review":
            entry["buyer_scope_unverified"] = True
            entry["price_or_payment_authorized"] = False
        if detail_limit:
            entry["request_refs"] = list(
                query.order_by(ref_field).values_list(ref_field, flat=True)
                .distinct()[:detail_limit]
            )
        categories.append(entry)
    return {
        "schema": "mojprop.sales_action_queue.v1",
        "as_of_utc": now.isoformat(),
        "categories": categories,
        "category_count": len(categories),
        "total_queue_entries": sum(c["count"] for c in categories),
        "independent_customer_count": None,
        "collected_revenue": None,
        "payment_or_delivery_automatically_approved": False,
        "note": "Categories overlap; counts are tasks, not independent customers or sales.",
    }


class Command(BaseCommand):
    help = "Show urgent Moj Prop sales follow-ups without charging, contacting or exporting buyer PII."

    def add_arguments(self, parser):
        parser.add_argument(
            "--details", action="store_true",
            help="Include limited internal request references (never names or emails).",
        )
        parser.add_argument("--limit", type=int, default=10)

    def handle(self, *args, **options):
        limit = options["limit"] if options["details"] else 0
        try:
            report = action_queue_snapshot(detail_limit=limit)
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(json.dumps(
            report, sort_keys=True, ensure_ascii=False, separators=(",", ":")
        ))
