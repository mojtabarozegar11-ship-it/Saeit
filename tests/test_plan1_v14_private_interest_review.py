"""No-network, nonpayable v1.4.1 buyer-comprehension regressions."""
import unittest
from datetime import datetime, timezone
from dataclasses import replace

from prop_firm.plan1_v14_private_interest_review import (
    review_nonpayable_v14_interest, ProspectiveInterestBlocked,
    ACKNOWLEDGMENTS, REQUIRED_FIELDS,
)
from prop_firm.plan1_v14_social_or_50_terms import review_prospective_terms

NOW = datetime(2026, 11, 17, 13, 0, tzinfo=timezone.utc)


def valid_form():
    terms=review_prospective_terms()
    f={key: True for key in ACKNOWLEDGMENTS}
    f.update(request_ref="REQUEST-ABCDEFGHIJKLMNOP",
             sku="MOJ-PROP-01", terms_version=terms.version,
             terms_digest_sha256=terms.contract_candidate_sha256,
             self_declared_country="CA", age_at_least_18_self_attested=True,
             request_information_only=True, marketing_consent=False)
    return f


def assess(f=None, t=NOW):
    return review_nonpayable_v14_interest(form=valid_form() if f is None else f,
                                         server_received_at=t)


class PrivateV14InterestTests(unittest.TestCase):
    def test_full_acknowledgment_schema_current(self):
        self.assertEqual(set(valid_form()), REQUIRED_FIELDS)

    def test_valid_private_interest_is_not_purchase(self):
        x=assess()
        self.assertEqual(x.state,"prospective_nonpayable_interest_only")
        self.assertFalse(x.paid_invoice_authorized)
        self.assertFalse(x.enrollment_authorized)
        self.assertFalse(x.real_orders_authorized)

    def test_no_fake_legal_or_broker_approval(self):
        x=assess()
        self.assertFalse(x.identity_independently_verified)
        self.assertFalse(x.age_independently_verified)
        self.assertFalse(x.broker_permission_verified)
        self.assertFalse(x.finance_and_advertising_law_cleared)
        self.assertFalse(x.contract_signed)

    def test_no_marketing_authority(self):
        self.assertFalse(assess().automated_marketing_authorized)

    def test_digest_exact_current_terms(self):
        self.assertEqual(assess().accepted_terms_sha256,review_prospective_terms().contract_candidate_sha256)

    def test_utc_timestamp(self):
        self.assertEqual(assess().received_at_utc,NOW.isoformat())

    def test_deterministic_inquiry_digest(self):
        self.assertEqual(assess().redacted_comprehension_sha256,assess().redacted_comprehension_sha256)
        self.assertEqual(len(assess().redacted_comprehension_sha256),64)

    def test_no_user_identity_is_collected(self):
        f=valid_form(); f["real_name"]="John Doe"
        with self.assertRaises(ProspectiveInterestBlocked): assess(f)

    def test_reject_legacy_v12_social_waiver_terms(self):
        f=valid_form();f["terms_version"]="2026-11-15/v1.2"
        with self.assertRaises(ProspectiveInterestBlocked):assess(f)

    def test_reject_stale_draft_digest(self):
        f=valid_form();f["terms_digest_sha256"]="0"*64
        with self.assertRaises(ProspectiveInterestBlocked):assess(f)

    def test_reject_old_unsigned_v13_version(self):
        f=valid_form();f["terms_version"]=review_prospective_terms().supersedes_unsigned_draft_version
        with self.assertRaises(ProspectiveInterestBlocked):assess(f)

    def test_reject_educational_product_sku(self):
        f=valid_form();f["sku"]="MOJPROP-STARTER30"
        with self.assertRaises(ProspectiveInterestBlocked):assess(f)

    def test_reject_missing_closed_total_ack(self):
        f=valid_form();f["ack_fifty_closed_positions_total_not_each_stage"]=False
        with self.assertRaises(ProspectiveInterestBlocked):assess(f)

    def test_reject_unacknowledged_six_days_per_stage(self):
        f=valid_form();f["ack_six_trading_days_in_each_stage"]=False
        with self.assertRaises(ProspectiveInterestBlocked):assess(f)

    def test_reject_unacknowledged_social_or_platform_choice(self):
        f=valid_form();f["ack_one_qualifying_original_instagram_or_facebook_post"]=False
        with self.assertRaises(ProspectiveInterestBlocked):assess(f)

    def test_reject_unacknowledged_672_hours(self):
        f=valid_form();f["ack_post_remains_public_for_at_least_672_hours"]=False
        with self.assertRaises(ProspectiveInterestBlocked):assess(f)

    def test_reject_unacknowledged_separate_clocks(self):
        f=valid_form();f["ack_social_clock_independent_from_trading_window"]=False
        with self.assertRaises(ProspectiveInterestBlocked):assess(f)

    def test_reject_no_promotional_disclosure(self):
        f=valid_form();f["ack_required_clear_promotion_relationship_disclosure"]=False
        with self.assertRaises(ProspectiveInterestBlocked):assess(f)

    def test_reject_no_legal_clearance_ack(self):
        f=valid_form();f["ack_social_requirement_subject_to_legal_clearance"]=False
        with self.assertRaises(ProspectiveInterestBlocked):assess(f)

    def test_reject_no_funding_disclosure_ack(self):
        f=valid_form();f["ack_30_native_trx_is_evaluation_not_broker_funding"]=False
        with self.assertRaises(ProspectiveInterestBlocked):assess(f)

    def test_reject_marketing_opt_in_to_info_flow(self):
        f=valid_form();f["marketing_consent"]=True
        with self.assertRaises(ProspectiveInterestBlocked):assess(f)

    def test_reject_boolean_as_text(self):
        f=valid_form();f["self_declared_country"]=True
        with self.assertRaises(ProspectiveInterestBlocked):assess(f)

    def test_reject_age_boolean_false(self):
        f=valid_form();f["age_at_least_18_self_attested"]=False
        with self.assertRaises(ProspectiveInterestBlocked):assess(f)

    def test_reject_numeric_ack_instead_of_true(self):
        f=valid_form();f["ack_28_day_trading_window"]=1
        with self.assertRaises(ProspectiveInterestBlocked):assess(f)

    def test_reject_no_request_purpose(self):
        f=valid_form();f["request_information_only"]=False
        with self.assertRaises(ProspectiveInterestBlocked):assess(f)

    def test_reject_short_request_reference(self):
        f=valid_form();f["request_ref"]="REQUEST-AAA"
        with self.assertRaises(ProspectiveInterestBlocked):assess(f)

    def test_reject_naive_timestamp(self):
        with self.assertRaises(ProspectiveInterestBlocked):
            assess(t=NOW.replace(tzinfo=None))

    def test_reject_unexpected_extra_email_field(self):
        f=valid_form();f["email"]="buyer@example.com"
        with self.assertRaises(ProspectiveInterestBlocked):assess(f)

    def test_reject_missing_privacy_ack(self):
        f=valid_form();f.pop("ack_purpose_specific_privacy_review")
        with self.assertRaises(ProspectiveInterestBlocked):assess(f)

    def test_no_buyer_auto_contact_from_request(self):
        self.assertFalse(assess().automated_marketing_authorized)


if __name__ == "__main__":
    unittest.main()
