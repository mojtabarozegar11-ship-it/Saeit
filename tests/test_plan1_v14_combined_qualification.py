"""Review-only tests: fifty verified closed positions AND social OR 28 days."""
import unittest
from dataclasses import replace

from prop_firm.plan1_v14_combined_qualification import review_v14_combined
from prop_firm.plan1_v14_social_or_50_terms import review_prospective_terms
from prop_firm.plan1_v14_social_or_28d_review import Social28DayReview
from prop_firm.xauusd_v13_qualification_preview import QualificationPreview


def phase_math(**kw):
    t=review_prospective_terms()
    vals=dict(
        sku="MOJ-PROP-01",
        contract_version=t.supersedes_unsigned_draft_version,
        reviewed_closed_positions=50,required_closed_positions=50,
        phase_one_math_pass=True,phase_two_math_pass=True,
        entire_challenge_math_pass=True,reasons=(),
    )
    vals.update(kw)
    return QualificationPreview(**vals)


def post_math(**kw):
    vals=dict(
        candidate_platform="instagram",
        observed_hours=672,observations=29,reasons=(),
        timeline_mathematically_consistent=True,
    )
    vals.update(kw)
    return Social28DayReview(**vals)


class CombinedV14ReviewTests(unittest.TestCase):
    def test_both_math_pass_still_noncommercial(self):
        x=review_v14_combined(phases=phase_math(),social=post_math())
        self.assertTrue(x.full_draft_math_satisfied)
        self.assertFalse(x.paid_enrollment_authorized)
        self.assertFalse(x.real_trading_authorized)
        self.assertFalse(x.payout_authorized)
        self.assertFalse(x.signed_customer_contract_verified)
        self.assertFalse(x.advertising_legally_approved)

    def test_facebook_or_instagram_can_satisfy_math(self):
        x=review_v14_combined(phases=phase_math(),social=post_math(candidate_platform="facebook"))
        self.assertTrue(x.social_post_math_satisfied)

    def test_fewer_than_fifty_cannot_pass(self):
        x=review_v14_combined(phases=phase_math(reviewed_closed_positions=49),social=post_math())
        self.assertFalse(x.phase_and_fifty_math_satisfied)
        self.assertFalse(x.full_draft_math_satisfied)

    def test_phase_two_not_passed(self):
        x=review_v14_combined(phases=phase_math(phase_two_math_pass=False),social=post_math())
        self.assertFalse(x.full_draft_math_satisfied)

    def test_phase_one_not_passed(self):
        x=review_v14_combined(phases=phase_math(phase_one_math_pass=False),social=post_math())
        self.assertFalse(x.full_draft_math_satisfied)

    def test_phase_reasons_present_fail(self):
        x=review_v14_combined(phases=phase_math(reasons=("evidence_missing",)),social=post_math())
        self.assertFalse(x.full_draft_math_satisfied)

    def test_stale_contract_version_rejected(self):
        with self.assertRaises(ValueError):
            review_v14_combined(phases=phase_math(contract_version="2026-11-15/v1.2"),social=post_math())

    def test_stale_sku_rejected(self):
        with self.assertRaises(ValueError):
            review_v14_combined(phases=phase_math(sku="MOJPROP-STARTER30"),social=post_math())

    def test_stale_required_count_rejected(self):
        with self.assertRaises(ValueError):
            review_v14_combined(phases=phase_math(required_closed_positions=100),social=post_math())

    def test_social_27_days_fails(self):
        x=review_v14_combined(phases=phase_math(),social=post_math(observed_hours=648))
        self.assertFalse(x.social_post_math_satisfied)
        self.assertIn("single_platform_twenty_eight_days_not_mathematically_proven",x.reasons)

    def test_social_inconsistent_rejected(self):
        x=review_v14_combined(phases=phase_math(),
                social=post_math(timeline_mathematically_consistent=False))
        self.assertFalse(x.full_draft_math_satisfied)

    def test_social_has_unresolved_reasons(self):
        x=review_v14_combined(phases=phase_math(),
                social=post_math(reasons=("unverified_snapshot",)))
        self.assertFalse(x.full_draft_math_satisfied)

    def test_other_social_platform_rejected(self):
        x=review_v14_combined(phases=phase_math(),social=post_math(candidate_platform="x"))
        self.assertFalse(x.social_post_math_satisfied)

    def test_social_without_fifty_not_enough(self):
        x=review_v14_combined(phases=phase_math(entire_challenge_math_pass=False),social=post_math())
        self.assertTrue(x.social_post_math_satisfied)
        self.assertFalse(x.full_draft_math_satisfied)

    def test_fifty_without_social_not_enough(self):
        x=review_v14_combined(phases=phase_math(),social=post_math(observed_hours=0))
        self.assertTrue(x.phase_and_fifty_math_satisfied)
        self.assertFalse(x.full_draft_math_satisfied)

    def test_typed_review_required(self):
        with self.assertRaises(ValueError):
            review_v14_combined(phases={"fifty":True},social=post_math())
        with self.assertRaises(ValueError):
            review_v14_combined(phases=phase_math(),social={"post":True})

    def test_digest_link_to_exact_new_terms(self):
        x=review_v14_combined(phases=phase_math(),social=post_math())
        y=review_prospective_terms()
        self.assertEqual(x.candidate_terms_sha256,y.contract_candidate_sha256)
        self.assertEqual(x.draft_contract_version,y.version)

if __name__=="__main__":
    unittest.main()
