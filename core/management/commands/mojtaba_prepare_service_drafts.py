"""Prepare internal, nonbinding service response drafts in the existing CRM.

Default mode is fully read-only. --apply writes only a consented inquiry's
internal_note/status and one PII-free AuditLog record; it does not contact
customers, set prices, create orders, or activate any sales channel.
"""
import json

from django.core.management.base import BaseCommand, CommandError

from core.service_quote_draft import (
    MAX_BATCH, BOT_ID, prepare_next, prepare_one, preview_candidates,
)


class Command(BaseCommand):
    help = (
        "One-bot CRM service proposal drafting; default preview, "
        "explicit --apply for internal notes only."
    )

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--limit", type=int, default=1)
        parser.add_argument("--inquiry-id", type=int)

    def handle(self, *args, **options):
        limit = options["limit"]
        inquiry_id = options.get("inquiry_id")
        if type(limit) is not int or not 1 <= limit <= MAX_BATCH:
            raise CommandError("limit must be 1..20")
        if inquiry_id is not None and (inquiry_id < 1 or limit != 1):
            raise CommandError("inquiry-id must be positive and limit must be 1")
        if not options["apply"]:
            if inquiry_id is not None:
                # Never print a prospect's name, email, phone or body.
                self.stdout.write(json.dumps({
                    "bot": BOT_ID, "mode": "read_only",
                    "explicit_inquiry_selected": True,
                    "changes": 0, "customer_contacted": False,
                    "verified_cash_revenue": None,
                }, sort_keys=True))
            else:
                self.stdout.write(json.dumps(
                    preview_candidates(limit), ensure_ascii=False, sort_keys=True
                ))
            return

        created = []
        blocked = {}
        for _ in range(limit):
            result = prepare_one(inquiry_id) if inquiry_id is not None else prepare_next()
            status = result["state"]
            if status == "prepared_internal_draft":
                created.append(result["evidence"]["inquiry_id"])
            else:
                blocked[status] = blocked.get(status, 0) + 1
                break
            if inquiry_id is not None:
                break

        self.stdout.write(json.dumps({
            "bot": BOT_ID,
            "mode": "internal_crm_draft_only",
            "prepared_count": len(created),
            "prepared_inquiry_ids": created,
            "blocked_categories": blocked,
            "email_sent": False,
            "sms_sent": False,
            "payment_enabled": False,
            "sale_or_delivery_verified": False,
            "cash_revenue_verified": None,
            "requires_human_review": True,
        }, ensure_ascii=False, sort_keys=True))
