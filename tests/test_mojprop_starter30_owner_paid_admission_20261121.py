"""Zero-cost offline tests for the immutable owner-approved paid-admission gate.

These cannot attest to actual treasury funds, lawful jurisdiction or completed
beneficiary payouts. No emails, customer records, DB connections or TRX calls.
"""
from dataclasses import replace
from types import ModuleType, SimpleNamespace
import sys
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from prop_firm import starter30_paid_admission as admission
from prop_firm import simulation_policy
from prop_firm import starter30_live


# These flags/references are purely fake in-process test values, never an
# attestation or approval for production customers.
FAKE_APPROVALS = {
    "MPW_MOJPROP_PAID_RULES_FINALLY_APPROVED": True,
    "MPW_MOJPROP_WRITTEN_PAID_TERMS_VERIFIED": True,
    "MPW_MOJPROP_QUALIFIED_PAYOUT_RESERVE_VERIFIED": True,
    "MPW_MOJPROP_REAL_REWARD_SETTLEMENT_VERIFIED": True,
    "MPW_MOJPROP_PAID_TERMS_EVIDENCE_REF": "offline-unit-test-terms-ref",
    "MPW_MOJPROP_REWARD_RESERVE_EVIDENCE_REF": "offline-unit-test-reserve-ref",
    "MPW_MOJPROP_REWARD_SETTLEMENT_EVIDENCE_REF": "offline-unit-test-rail-ref",
}


def _mock_effective_scorer(**changes):
    values = dict(admission._EFFECTIVE_SCORER)
    values["version"] = simulation_policy.SIMULATION_POLICY.contract_version
    values.update(changes)
    module = ModuleType("prop_firm.rules")
    module.POLICY = SimpleNamespace(**values)
    return module


class Starter30OwnerPaidAdmissionTests(SimpleTestCase):
    def test_current_approved_terms_are_specified_without_legacy_70_30(self):
        p = simulation_policy.SIMULATION_POLICY
        self.assertEqual(p.canonical_best_day_share_pct, 50)
        self.assertEqual(p.trader_eligible_profit_share_pct, 100)
        self.assertEqual(p.company_eligible_profit_share_pct, 0)
        self.assertEqual(p.challenge_window_days, 60)
        self.assertEqual(p.starting_balance_usd, 1000)
        self.assertEqual(p.first_payout_min_activity_days, 14)
        self.assertEqual(p.subsequent_payout_interval_days, 14)
        self.assertEqual(p.minimum_payout_request_usd, 10)
        self.assertTrue(p.transfer_network_fees_paid_by_company)
        self.assertTrue(p.entry_fee_refund_with_first_successful_profit_withdrawal)
        self.assertFalse(p.customer_deposit_required)
        self.assertFalse(p.real_orders_enabled)

    @override_settings(**FAKE_APPROVALS)
    def test_missing_effective_rules_source_always_refuses_new_invoice(self):
        with patch.dict(sys.modules, {"prop_firm.rules": None}):
            defects = admission.paid_admission_defects()
        self.assertIn("effective_scoring_contract_unavailable", defects)

    @override_settings(**FAKE_APPROVALS)
    def test_legacy_32pct_and_70_30_are_explicitly_rejected(self):
        with patch.dict(sys.modules, {"prop_firm.rules": _mock_effective_scorer(
            best_day_share_pct=32, trader_profit_share_pct=70,
            company_profit_share_pct=30,
        )}):
            defects = admission.paid_admission_defects()
        self.assertIn("effective_scorer_best_day_share_pct_mismatch", defects)
        self.assertIn("effective_scorer_trader_profit_share_pct_mismatch", defects)
        self.assertIn("effective_scorer_company_profit_share_pct_mismatch", defects)

    @override_settings(**FAKE_APPROVALS)
    def test_wrong_contract_version_refused_even_with_right_numbers(self):
        with patch.dict(sys.modules, {"prop_firm.rules": _mock_effective_scorer(
            version="historical-unapproved-version",
        )}):
            defects = admission.paid_admission_defects()
        self.assertIn("scoring_contract_version_mismatch", defects)

    @override_settings(**FAKE_APPROVALS)
    def test_stale_canonical_consistency_policy_is_detected(self):
        legacy = replace(
            simulation_policy.SIMULATION_POLICY,
            canonical_best_day_share_pct=simulation_policy.D("32"),
        )
        with (
            patch.object(admission, "SIMULATION_POLICY", legacy),
            patch.dict(sys.modules, {"prop_firm.rules": _mock_effective_scorer()}),
        ):
            defects = admission.paid_admission_defects()
        self.assertIn("new_offer_canonical_best_day_share_pct_mismatch", defects)

    @override_settings(**FAKE_APPROVALS)
    def test_old_or_changed_payout_ledger_percentage_is_refused(self):
        from prop_firm import simulation_payout
        with (
            patch.dict(sys.modules, {"prop_firm.rules": _mock_effective_scorer()}),
            patch.object(simulation_payout, "PAYOUT_PERCENT", 70),
        ):
            defects = admission.paid_admission_defects()
        self.assertIn("verified_profit_commitment_not_100_percent", defects)

    def test_unapproved_cash_reserve_and_real_transfer_rail_hold(self):
        with (
            patch.dict(sys.modules, {"prop_firm.rules": _mock_effective_scorer()}),
            override_settings(
                MPW_MOJPROP_PAID_RULES_FINALLY_APPROVED=False,
                MPW_MOJPROP_WRITTEN_PAID_TERMS_VERIFIED=False,
                MPW_MOJPROP_QUALIFIED_PAYOUT_RESERVE_VERIFIED=False,
                MPW_MOJPROP_REAL_REWARD_SETTLEMENT_VERIFIED=False,
                MPW_MOJPROP_PAID_TERMS_EVIDENCE_REF="",
                MPW_MOJPROP_REWARD_RESERVE_EVIDENCE_REF="",
                MPW_MOJPROP_REWARD_SETTLEMENT_EVIDENCE_REF="",
            ),
        ):
            defects = admission.paid_admission_defects()
        self.assertIn("real_reward_reserve_unverified", defects)
        self.assertIn("real_payout_rail_unverified", defects)
        self.assertIn("accepted_paid_rules_not_approved", defects)
        self.assertIn("private_paid_terms_evidence_reference_missing", defects)

    @override_settings(**FAKE_APPROVALS)
    def test_complete_mock_evidence_only_proves_deterministic_local_invariants(self):
        with patch.dict(sys.modules, {"prop_firm.rules": _mock_effective_scorer()}):
            self.assertEqual(admission.paid_admission_defects(), ())
            admission.require_paid_admission_readiness()
        # This deliberately makes NO claim about real accounts or capital.

    def test_new_invoice_preflight_refuses_before_identity_db_or_customer_otp(self):
        with (
            patch.object(starter30_live, "require_release"),
            patch.object(starter30_live, "_provider_pair", return_value=(object(), object())),
            patch.object(starter30_live, "approved_recipient", return_value="offline-only-public-address"),
            patch.object(starter30_live, "_hex_recipient", return_value="41" + "0" * 40),
            patch.object(starter30_live, "attested_receivers", return_value=("offline-only-address",)),
            patch("prop_firm.starter30_checkout_email.require_email_verification_release"),
            patch.object(starter30_live, "normalize_email") as normalized,
            patch.object(starter30_live.PropSimulationIdentity, "objects") as identities,
            patch.dict(sys.modules, {"prop_firm.rules": None}),
        ):
            with self.assertRaises(admission.Starter30PaidAdmissionHold):
                starter30_live.issue_invoice(
                    email="nobody@example.invalid",
                    payer_address="",
                    terms_accepted=True,
                    email_proof="offline-invalid",
                )
            normalized.assert_not_called()
            identities.using.assert_not_called()

    def test_hold_message_never_contains_private_evidence_or_bank_details(self):
        with patch.dict(sys.modules, {"prop_firm.rules": None}):
            with self.assertRaises(admission.Starter30PaidAdmissionHold) as caught:
                admission.require_paid_admission_readiness()
        message = str(caught.exception)
        self.assertIn("on hold", message)
        self.assertNotIn("offline-unit-test", message)
        self.assertNotIn("wallet", message.lower())
