"""Isolated DB regression: OTP binds to the existing consented PropInterest.

All identities, emails, timestamps and HMAC keys are synthetic. This bridge
DOES NOT send mail or permit sales, marketing, demo activation or broker KYC.
"""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch
from django.test import TestCase

from prop_firm.lead_models import PropInterest
from prop_firm.models import PropChallengeEnrollment, PropAccount
from prop_firm.buyer_order_review import Plan1OrderGateClosed
from prop_firm.plan1_orm_consent_review import review_email_verified_existing_interest
from test_prop_plan1_canonical_interest_bridge import (
    args as consent_args, sign as consent_sign,
)
from test_prop_plan1_demo_email_interest import (
    OTP_KEY, NOW, receipt as otp_receipt, sign as otp_sign,
)


class RealDatabaseDemoEmailConsentTests(TestCase):
    def setUp(self):
        self.interest = PropInterest.objects.create(
            email="synthetic-demo-otp@example.invalid",
            plan_code="MOJ-PROP-01",
            consent_version="moj-prop-interest-v1",
            source_language="en",
            status="new",
        )

    def data(self):
        c = consent_args()
        att = dict(c["trusted_consent_attestation"])
        att["interest_pk"] = self.interest.pk
        otp = otp_receipt()
        otp["interest_pk"] = self.interest.pk
        otp["inquiry_sha256"] = c["expected_inquiry_sha256"]
        return dict(
            actor=SimpleNamespace(
                is_authenticated=True, is_active=True, is_staff=True,
                is_superuser=True,
                has_perm=lambda p: p == "prop_firm.view_propinterest",
            ),
            interest_pk=self.interest.pk,
            inquiry=c["inquiry"],
            consent_attestation=att,
            consent_tag_hex=consent_sign(att),
            consent_key=c["trusted_consent_key"],
            request_ref=c["expected_request_ref"],
            inquiry_sha256=c["expected_inquiry_sha256"],
            consent_evidence_sha256=c["expected_consent_evidence_sha256"],
            signed_otp_receipt=otp,
            signed_otp_tag_hex=otp_sign(otp),
            trusted_otp_service_key=OTP_KEY,
            declared_country="DE",
            age_18_self_attested=True,
        )

    def review(self, data=None):
        if data is None:
            data=self.data()
        now = datetime.fromtimestamp(NOW, timezone.utc)
        with patch("prop_firm.plan1_orm_consent_review.timezone.now", return_value=now):
            return review_email_verified_existing_interest(**data)

    def test_real_existing_optin_signed_otp_is_private_only(self):
        result=self.review()
        self.assertEqual(result.interest_pk, self.interest.pk)
        self.assertEqual(result.stage, "PRIVATE_EMAIL_VERIFIED_INTEREST_ONLY")

    def test_canonical_row_not_mutated_after_review(self):
        before=PropInterest.objects.get(pk=self.interest.pk)
        result=self.review()
        after=PropInterest.objects.get(pk=self.interest.pk)
        self.assertEqual((after.email,after.status,after.updated_at),
                         (before.email,before.status,before.updated_at))
        self.assertFalse(result.payment_authorized)

    def test_no_challenge_enrollment_created(self):
        self.review()
        self.assertFalse(PropChallengeEnrollment.objects.exists())

    def test_no_real_or_demo_account_created(self):
        self.review()
        self.assertFalse(PropAccount.objects.exists())

    def test_no_contact_authority_created(self):
        self.assertFalse(self.review().contact_permission_created)

    def test_no_marketing_authority_created(self):
        self.assertFalse(self.review().marketing_consent)

    def test_no_full_legal_kyc_by_email(self):
        result=self.review()
        self.assertFalse(result.buyer_legal_age_verified)
        self.assertFalse(result.buyer_country_legally_permitted)
        self.assertFalse(result.actual_kyc_verified)

    def test_real_broker_account_not_required_from_otp(self):
        self.assertFalse(self.review().live_litefinance_account_required_for_demo)

    def test_existing_withdrawn_optin_blocks_otp_join(self):
        self.interest.status="withdrawn"
        self.interest.save()
        with self.assertRaises(Plan1OrderGateClosed):
            self.review()
        self.assertEqual(PropInterest.objects.get(pk=self.interest.pk).status, "withdrawn")

    def test_existing_contacted_optin_blocks_fresh_otp_review(self):
        self.interest.status="contacted"
        self.interest.save()
        with self.assertRaises(Plan1OrderGateClosed):
            self.review()

    def test_educational_sku_cannot_use_existing_optin(self):
        self.interest=PropInterest.objects.create(
            email="synthetic-other-starter@example.invalid",
            plan_code="MOJPROP-STARTER30",
            consent_version="moj-prop-interest-v1",
            source_language="en",
        )
        with self.assertRaises(Plan1OrderGateClosed):
            self.review()

    def test_wrong_signed_otp_receipt_cannot_be_reused(self):
        data=self.data()
        data["signed_otp_receipt"]["interest_pk"]+=1
        data["signed_otp_tag_hex"]=otp_sign(data["signed_otp_receipt"])
        with self.assertRaises(Plan1OrderGateClosed):
            self.review(data)

    def test_valid_otp_from_other_consent_request_denied(self):
        data=self.data()
        data["signed_otp_receipt"]["request_ref"]="REQUEST-ZYXWVUTSRQPONMLK"
        data["signed_otp_tag_hex"]=otp_sign(data["signed_otp_receipt"])
        with self.assertRaises(Plan1OrderGateClosed):
            self.review(data)

    def test_fake_otp_signature_denied(self):
        data=self.data()
        data["signed_otp_tag_hex"]="f"*64
        with self.assertRaises(Plan1OrderGateClosed):
            self.review(data)

    def test_otp_from_same_key_as_consent_registry_denied(self):
        data=self.data()
        data["trusted_otp_service_key"]=data["consent_key"]
        with self.assertRaises(Plan1OrderGateClosed):
            self.review(data)

    def test_staff_with_no_private_crm_permission_denied(self):
        data=self.data()
        data["actor"].has_perm=lambda _: False
        with self.assertRaises(Plan1OrderGateClosed):
            self.review(data)

    def test_non_superuser_staff_denied(self):
        data=self.data()
        data["actor"].is_superuser=False
        with self.assertRaises(Plan1OrderGateClosed):
            self.review(data)

    def test_inactive_reviewer_denied(self):
        data=self.data()
        data["actor"].is_active=False
        with self.assertRaises(Plan1OrderGateClosed):
            self.review(data)

    def test_false_age_self_attestation_denied(self):
        data=self.data()
        data["age_18_self_attested"]=False
        with self.assertRaises(Plan1OrderGateClosed):
            self.review(data)

    def test_wrong_country_declaration_denied(self):
        data=self.data()
        data["declared_country"]="Germany"
        with self.assertRaises(Plan1OrderGateClosed):
            self.review(data)

    def test_email_proof_still_cannot_issue_payment(self):
        result=self.review()
        self.assertFalse(result.payable_invoice)
        self.assertFalse(result.demo_account_activated)
        self.assertFalse(result.real_account_activated)

    def test_otp_interest_does_not_require_paid_purchase_contract(self):
        result=self.review()
        self.assertFalse(result.buyer_signed_contract_verified)
        self.assertFalse(result.purchase_legality_verified)

    def test_no_private_contract_draft_expected_in_otp_path(self):
        data=self.data()
        self.assertNotIn("private_order_draft", data)
        self.assertFalse(self.review(data).payable_invoice)
