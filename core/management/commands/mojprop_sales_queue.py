"""Print a bounded, non-PII Moj Prop sales queue.

This is an owner-operator read-only command. It does not send email, advance a
lead, create a payment intent, issue a quote or execute a trade.
"""
from __future__ import annotations

import json

from django.core.management.base import BaseCommand, CommandError

from core.models import MojPropRequest
from core.mojprop_sales_queue import QUEUE_STATUSES, summarise_queue


class Command(BaseCommand):
    help = "Print a bounded, privacy-preserving Moj Prop sales queue as JSON."

    def add_arguments(self, parser):
        parser.add_argument(
            "--status",
            choices=QUEUE_STATUSES + ("closed", "spam"),
            help="Limit the queue to one lead status",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=25,
            help="Maximum rows to print (1-100; default: 25)",
        )

    def handle(self, *args, **options):
        limit = options["limit"]
        if type(limit) is not int or not 1 <= limit <= 100:
            raise CommandError("limit must be an integer between 1 and 100")

        queryset = MojPropRequest.objects.all().order_by("-created_at", "-id")
        status = options.get("status")
        if status:
            queryset = queryset.filter(status=status)
        payload = summarise_queue(list(queryset[:limit]))
        self.stdout.write(json.dumps(payload, ensure_ascii=False, sort_keys=True))
