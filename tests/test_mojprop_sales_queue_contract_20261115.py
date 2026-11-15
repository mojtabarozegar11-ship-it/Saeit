"""Pure contract tests for the non-PII Moj Prop operator queue."""
from __future__ import annotations

from datetime import datetime, timezone
import unittest

from core.mojprop_sales_queue import offer_draft_eligible, summarise_queue


class Lead:
    pk = 1
    status = "reviewing"
    consent = True
    request_id = "MOJPROP-20261115-ABCD1234"
    route = "research"
    horizon = "week"
    name = "A customer"
    email = "buyer@example.com"
    notes = "A sufficiently detailed commercial research objective."
    created_at = datetime(2026, 11, 15, 12, 0, tzinfo=timezone.utc)


class MojPropSalesQueueContractTests(unittest.TestCase):
    def test_reviewed_consented_lead_is_eligible_without_exposing_pii(self):
        payload = summarise_queue([Lead()])
        self.assertEqual(payload["offer_draft_eligible"], 1)
        row = payload["rows"][0]
        self.assertNotIn("name", row)
        self.assertNotIn("email", row)
        self.assertNotIn("notes", row)
        self.assertFalse(payload["side_effects"]["email_sent"])

    def test_new_lead_is_not_eligible_for_offer_draft(self):
        lead = Lead()
        lead.status = "new"
        self.assertFalse(offer_draft_eligible(lead))
        self.assertEqual(summarise_queue([lead])["by_status"]["new"], 1)

    def test_missing_consent_or_short_scope_is_not_eligible(self):
        for attribute, value in (("consent", False), ("notes", "too short"), ("email", "")):
            lead = Lead()
            setattr(lead, attribute, value)
            with self.subTest(attribute=attribute):
                self.assertFalse(offer_draft_eligible(lead))

    def test_queue_has_explicit_no_side_effect_contract(self):
        payload = summarise_queue([])
        self.assertEqual(payload["total"], 0)
        self.assertFalse(payload["side_effects"]["payment_created"])
        self.assertFalse(payload["side_effects"]["lead_mutated"])
        self.assertFalse(payload["side_effects"]["trade_executed"])


if __name__ == "__main__":
    unittest.main()
