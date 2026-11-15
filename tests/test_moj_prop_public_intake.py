"""Tests for the non-financial Moj Prop applicant intake contract."""
from __future__ import annotations

from unittest import TestCase

from prop_firm.public_intake import (
    CONSENT_VERSION,
    RISK_DISCLOSURE_VERSION,
    model_defaults,
    public_result,
    screen_applicant,
)


def valid_kwargs():
    return {
        "email": "  Buyer@example.com ",
        "preferred_language": "fa",
        "jurisdiction": "CA",
        "source": "mojtaba.bot.ai",
        "consent_version": CONSENT_VERSION,
        "risk_disclosure_version": RISK_DISCLOSURE_VERSION,
        "risk_acknowledged": True,
    }


class PublicIntakeTests(TestCase):
    def test_valid_lead_is_normalized_and_persistable(self):
        decision = screen_applicant(**valid_kwargs())
        self.assertTrue(decision.accepted)
        self.assertTrue(decision.persistence_allowed)
        self.assertEqual(decision.normalized_email, "buyer@example.com")
        self.assertEqual(decision.preferred_language, "fa")
        self.assertEqual(decision.blockers, ())
        self.assertEqual(model_defaults(decision)["status"], "new")

    def test_valid_lead_never_enables_money_movement(self):
        decision = screen_applicant(**valid_kwargs())
        self.assertFalse(decision.checkout_enabled)
        self.assertFalse(decision.trading_enabled)
        self.assertFalse(decision.payout_enabled)

    def test_missing_consent_blocks_persistence(self):
        values = valid_kwargs()
        values["consent_version"] = "old"
        decision = screen_applicant(**values)
        self.assertFalse(decision.accepted)
        self.assertFalse(decision.persistence_allowed)
        self.assertIn("consent_version_required", decision.blockers)

    def test_missing_risk_acknowledgement_blocks_persistence(self):
        values = valid_kwargs()
        values["risk_acknowledged"] = 1
        decision = screen_applicant(**values)
        self.assertFalse(decision.accepted)
        self.assertIn("risk_disclosure_not_acknowledged", decision.blockers)

    def test_invalid_email_is_not_returned(self):
        values = valid_kwargs()
        values["email"] = "not-an-email"
        decision = screen_applicant(**values)
        self.assertFalse(decision.accepted)
        self.assertIsNone(decision.normalized_email)
        self.assertIn("invalid_email", decision.blockers)

    def test_control_character_is_rejected(self):
        values = valid_kwargs()
        values["jurisdiction"] = "CA\noperator"
        decision = screen_applicant(**values)
        self.assertFalse(decision.accepted)
        self.assertIn("invalid_jurisdiction", decision.blockers)

    def test_unsupported_source_is_rejected(self):
        values = valid_kwargs()
        values["source"] = "unknown-redirect"
        decision = screen_applicant(**values)
        self.assertFalse(decision.accepted)
        self.assertIn("unsupported_source", decision.blockers)

    def test_unsupported_language_is_rejected(self):
        values = valid_kwargs()
        values["preferred_language"] = "xx"
        decision = screen_applicant(**values)
        self.assertFalse(decision.accepted)
        self.assertIn("unsupported_language", decision.blockers)

    def test_public_result_does_not_echo_contact_data(self):
        decision = screen_applicant(**valid_kwargs())
        response = public_result(decision)
        self.assertNotIn("buyer@example.com", str(response))
        self.assertFalse(response["checkout_enabled"])
        self.assertEqual(response["next_step"], "owner_review_pending")

    def test_rejected_decision_cannot_be_converted_to_model_defaults(self):
        values = valid_kwargs()
        values["risk_disclosure_version"] = "old"
        decision = screen_applicant(**values)
        with self.assertRaises(ValueError):
            model_defaults(decision)

    def test_duplicate_blockers_are_not_emitted(self):
        values = valid_kwargs()
        values["source"] = ""
        decision = screen_applicant(**values)
        self.assertEqual(len(decision.blockers), len(set(decision.blockers)))
