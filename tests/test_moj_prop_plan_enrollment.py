"""Persist ten-plan purchase identity and reject tier switching or forged capital."""
from datetime import datetime, timezone
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from prop_firm.models import PropAccount, PropTrader, PropChallengeEnrollment
from prop_firm.plans import CHALLENGE_PLANS, DEFAULT_PLAN_CODE


class PurchasedPlanBindingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User=get_user_model()
        cls.user=User.objects.create_user(username="plan_buyer_ci",password="ci-only")
        cls.other=User.objects.create_user(username="plan_foreign_ci",password="ci-only")
        cls.profile=PropTrader.objects.create(user=cls.user)
        cls.other_profile=PropTrader.objects.create(user=cls.other)

    def purchase(self, plan_code="MOJ-PROP-06", invoice="ci-private-invoice-001"):
        return PropChallengeEnrollment.objects.create(
            trader=self.profile,verified_invoice_ref=invoice,
            confirmed_at=datetime(2026,10,1,tzinfo=timezone.utc),
            settlement_verified=True,plan_code=plan_code,
        )

    def phase(self, enrollment, tier_index, capital_usd, trader=None,
              kind=PropAccount.Kind.PHASE_ONE):
        return PropAccount.objects.create(
            trader=trader or self.profile,kind=kind,
            tier_index=tier_index,starting_capital_usd=Decimal(str(capital_usd)),
            challenge_enrollment=enrollment,
        )

    def test_default_first_plan_is_backward_compatible(self):
        purchase=self.purchase(plan_code=DEFAULT_PLAN_CODE)
        self.assertEqual(purchase.plan_code,"MOJ-PROP-01")
        first=self.phase(purchase,0,100)
        self.assertEqual(first.starting_capital_usd,Decimal("100"))

    def test_each_of_ten_plans_binds_simulated_account_to_correct_tier(self):
        for p in CHALLENGE_PLANS:
            with self.subTest(plan=p.code):
                purchase=self.purchase(p.code,invoice=f"invoice-{p.number}")
                stage1=self.phase(purchase,p.starting_tier_index,p.starting_capital_usd)
                stage2=self.phase(purchase,p.starting_tier_index,
                                  p.starting_capital_usd,
                                  kind=PropAccount.Kind.PHASE_TWO)
                self.assertEqual(stage1.challenge_enrollment_id,purchase.pk)
                self.assertEqual(stage2.challenge_enrollment_id,purchase.pk)
                self.assertEqual(stage1.tier_index,p.starting_tier_index)

    def test_selling_large_capital_plan_cannot_create_100_dollar_trial(self):
        enrollment=self.purchase("MOJ-PROP-10")
        with self.assertRaises(ValidationError):
            self.phase(enrollment,0,100)

    def test_mismatched_tier_and_capital_rejected(self):
        enrollment=self.purchase("MOJ-PROP-06")
        with self.assertRaises(ValidationError):
            self.phase(enrollment,5,100)
        with self.assertRaises(ValidationError):
            self.phase(enrollment,0,3000)

    def test_foreign_person_cannot_use_purchase_for_challenge(self):
        enrollment=self.purchase()
        with self.assertRaises(ValidationError):
            self.phase(enrollment,5,3000,trader=self.other_profile)

    def test_purchase_code_immutable_after_confirmed_purchase(self):
        enrollment=self.purchase()
        enrollment.plan_code="MOJ-PROP-10"
        with self.assertRaises(ValidationError):
            enrollment.save()
        enrollment.refresh_from_db()
        self.assertEqual(enrollment.plan_code,"MOJ-PROP-06")

    def test_receipt_and_buyer_identity_cannot_be_switched(self):
        enrollment=self.purchase()
        enrollment.verified_invoice_ref="replacement-invoice"
        with self.assertRaises(ValidationError):
            enrollment.save()
        enrollment.refresh_from_db()
        enrollment.trader=self.other_profile
        with self.assertRaises(ValidationError):
            enrollment.save()

    def test_unknown_plan_cannot_enter_purchase_ledger(self):
        with self.assertRaises(ValidationError):
            self.purchase("MOJ-PROP-77")

    def test_funded_level_cannot_be_below_purchased_start(self):
        enrollment=self.purchase("MOJ-PROP-10")
        with self.assertRaises(ValidationError):
            PropAccount.objects.create(
                trader=self.profile,kind=PropAccount.Kind.FUNDED,
                tier_index=0,starting_capital_usd=Decimal("100"),
                reference="private-broker-ci",challenge_enrollment=enrollment,
            )
        funded=PropAccount.objects.create(
            trader=self.profile,kind=PropAccount.Kind.FUNDED,
            tier_index=9,starting_capital_usd=Decimal("35000"),
            reference="private-broker-ci",challenge_enrollment=enrollment,
        )
        self.assertEqual(funded.tier_index,9)

    def test_unpurchased_legacy_trial_keeps_old_baseline(self):
        trial=PropAccount.objects.create(
            trader=self.profile,kind=PropAccount.Kind.PHASE_ONE,
        )
        self.assertEqual(trial.starting_capital_usd,Decimal("100"))
        self.assertEqual(trial.tier_index,0)
