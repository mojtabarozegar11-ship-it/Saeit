"""Management-command contract: quote output is evidence, not payment."""
from io import StringIO
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from django.core.management import call_command

class MojPropQuoteCommandTests(TestCase):
    def test_command_emits_snapshot_without_payment_fields(self):
        now = datetime.now(timezone.utc)
        offer = SimpleNamespace(
            lead=SimpleNamespace(request_id="MOJPROP-20261115-CMD1"),
            version=1, title="Command quote",
            scope="A source-backed manual report with explicit scope, limits and delivery conditions.",
            exclusions="No trading, no guarantees and no automatic advice.",
            amount=Decimal("25.00"), currency="USD", delivery_days=3,
            status="issued", reviewed_at=now - timedelta(hours=1),
            issued_at=now - timedelta(minutes=30),
            expires_at=now + timedelta(days=1),
            accepted_at=None, acceptance_reference="",
        )
        output = StringIO()
        with patch("core.management.commands.mojprop_quote_snapshot.MojPropOffer.objects.select_related") as select:
            select.return_value.get.return_value = offer
            with patch("core.management.commands.mojprop_quote_snapshot.make_quote_snapshot") as snapshot:
                snapshot.return_value = {
                    "reference": offer.lead.request_id,
                    "payment_status": "not_collected",
                    "delivery_status": "not_delivered",
                    "payable": False,
                }
                call_command("mojprop_quote_snapshot", offer_id=1, stdout=output)
        rendered = output.getvalue()
        self.assertIn("not_collected", rendered)
        self.assertIn("not_delivered", rendered)
        self.assertNotIn("tx_id", rendered)
        self.assertNotIn("payment_url", rendered)

if __name__ == "__main__":
    import unittest
    unittest.main()
