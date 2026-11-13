"""Owner-operated read-only cTrader gold snapshot -> private signal preview.

The command does not contact a broker, use wallet keys, write a DB task,
publish a signal or execute an order. It consumes a pre-existing private
one-shot DEMO capture prepared by the local cTrader operator.
"""
from __future__ import annotations

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from core.mojtrade_gold_capture import (
    GoldCaptureError, preview_private_gold_capture,
)


class Command(BaseCommand):
    help = (
        "Verify one existing private one-shot XAUUSD H1 DEMO log and "
        "calculate a nonexecutable Mojtaba.bot.ai signal preview. "
        "Does not trade, publish, charge, or validate broker authenticity."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--input", type=Path, required=True,
            help="Absolute existing private .log file in mode-0700 directory",
        )

    def handle(self, *args, **options):
        try:
            result = preview_private_gold_capture(options["input"])
        except GoldCaptureError as exc:
            raise CommandError("MOJTABA_GOLD_CAPTURE_BLOCKED: " + str(exc)) from exc

        # No raw account number, cTID or password is present in this report.
        # Keep the command output in the authorized operator's private console.
        self.stdout.write(json.dumps(
            result, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        ))
