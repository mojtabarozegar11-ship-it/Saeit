"""Cycle B signed-contract-to-ORM handoff regression. Synthetic evidence only.

These tests verify that no real documents, KYC, settlement, customer contact,
order issuance, accounts, funds or social posts are authorized by the adapter.
"""
from contextlib import nullcontext
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch
import copy

from django.test import SimpleTestCase

from prop_firm.buyer_order_review import Plan1OrderGateClosed
from prop_firm.order_readiness import REQUIRED
from prop_firm.plan1_orm_consent_review import (
    review_verified_precontract_for_interest,
)
from prop_firm.plan1_private_order_draft import _DOCUMENT_BINDINGS
from test_prop_buyer_precontract_chain import NOW, sign
from test_prop_plan1_private_order_draft import inputs as review_inputs
from test_prop_plan1_canonical_interest_bridge import args as consent_args


class Plan1VerifiedOrmHandoffTests(SimpleTestCase):
    """No database writes, actual identity papers or wallet activity."""

    def fixture(self):
        data = review_inputs()
        data.pop("server_now_sec")
        data["request_ref"] = data.pop("expected_request_ref")
        data["trusted_documents"] = {
            k: data.pop(k) for k in _DOCUMENT_BINDINGS.values()
        }
        c = consent_args()
        data.update(
            actor=SimpleNamespace(
                is_authenticated=True, is_active=True, is_staff=True,
                has_perm=lambda p: p == "prop_firm.view_propinterest",
            ),
            interest_pk=17,
            consent_attestation=c["trusted_consent_attestation"],
            consent_tag_hex=c["signed_consent_tag_hex"],
            consent_key=c["trusted_consent_key"],
            inquiry_sha256=c["expected_inquiry_sha256"],
            consent_evidence_sha256=c["expected_consent_evidence_sha256"],
        )
        return data, c["canonical_interest"]

    def run_review(self, data=None, *, row=None, server_now=NOW):
        if data is None:
            data, default_row = self.fixture()
        else:
            _, default_row = self.fixture()
        row = default_row if row is None else row
        clock = datetime.fromtimestamp(server_now, timezone.utc)
        with patch("prop_firm.plan1_orm_consent_review.timezone.now",
                   return_value=clock), \
             patch("prop_firm.plan1_orm_consent_review.transaction.atomic",
                   return_value=nullcontext()), \
             patch("prop_firm.plan1_orm_consent_review.PropInterest") as model:
            model.objects.select_for_update.return_value.filter.return_value.values.return_value.first.return_value = row
            outcome = review_verified_precontract_for_interest(**data)
            self.assertEqual(model.objects.select_for_update.call_count, 1)
            return outcome

    def deny(self, **changed):
        data, _ = self.fixture()
        data.update(changed)
        with self.assertRaises(Plan1OrderGateClosed):
            self.run_review(data)

    def test_real_canonical_row_is_bound_to_signed_private_review(self):
        result = self.run_review()
        self.assertEqual((result.interest_pk, result.state),
                         (17, "PRIVATE_SIGNED_EVIDENCE_REVIEW_ONLY"))
        self.assertTrue(result.private_review_ref.startswith("PROP1-REVIEW-"))

    def test_exact_single_plan1_native_trx_provenance_only(self):
        result = self.run_review()
        self.assertEqual(result.request_ref, "REQUEST-ABCDEFGHIJKLMNOP")
        self.assertEqual(len(result.contract_pdf_sha256), 64)

    def test_no_customer_contact_permission(self):
        self.assertFalse(self.run_review().contact_authorized)

    def test_no_marketing_consent_inferred(self):
        self.assertFalse(self.run_review().marketing_authorized)

    def test_no_payable_invoice_created(self):
        self.assertFalse(self.run_review().payable_invoice_created)

    def test_no_payment_confirmation_created(self):
        self.assertFalse(self.run_review().payment_confirmed)

    def test_no_challenge_enrollment_created(self):
        self.assertFalse(self.run_review().enrollment_created)

    def test_no_real_broker_account_created(self):
        self.assertFalse(self.run_review().funded_account_created)

    def test_no_kyc_attestation_manufactured(self):
        self.assertFalse(self.run_review().kyc_independently_proven_by_this_code)

    def test_no_signed_contract_legality_claim(self):
        self.assertFalse(self.run_review().executed_contract_independently_proven_by_this_code)

    def test_no_seller_license_claim(self):
        self.assertFalse(self.run_review().seller_license_independently_proven_by_this_code)

    def test_no_real_funding_claim(self):
        self.assertFalse(self.run_review().capital_available_independently_proven_by_this_code)

    def test_output_excludes_email_and_personal_documents(self):
        self.assertNotIn("synthetic@example.invalid", repr(self.run_review()))
        self.assertNotIn("passport", repr(self.run_review()).lower())

    def test_handoff_cannot_be_mutated_into_paid(self):
        with self.assertRaises(FrozenInstanceError):
            self.run_review().payment_confirmed = True

    def test_anonymous_actor_denied(self):
        data, _ = self.fixture()
        data["actor"].is_authenticated = False
        with self.assertRaises(Plan1OrderGateClosed):
            self.run_review(data)

    def test_inactive_actor_denied(self):
        data, _ = self.fixture()
        data["actor"].is_active = False
        with self.assertRaises(Plan1OrderGateClosed):
            self.run_review(data)

    def test_nonstaff_actor_denied(self):
        data, _ = self.fixture()
        data["actor"].is_staff = False
        with self.assertRaises(Plan1OrderGateClosed):
            self.run_review(data)

    def test_staff_missing_explicit_crm_permission_denied(self):
        data, _ = self.fixture()
        data["actor"].has_perm = lambda _p: False
        with self.assertRaises(Plan1OrderGateClosed):
            self.run_review(data)

    def test_permission_method_failure_denied(self):
        data, _ = self.fixture()
        def failed(_p):
            raise RuntimeError("permission provider unavailable")
        data["actor"].has_perm = failed
        with self.assertRaises(Plan1OrderGateClosed):
            self.run_review(data)

    def test_boolean_interest_pk_denied(self):
        self.deny(interest_pk=True)

    def test_wrong_interest_pk_denied(self):
        self.deny(interest_pk=999)

    def test_all_three_signature_key_roles_must_be_distinct(self):
        data, _ = self.fixture()
        data["consent_key"] = data["trusted_intake_key"]
        with self.assertRaises(Plan1OrderGateClosed):
            self.run_review(data)

    def test_missing_consent_signature_denied(self):
        self.deny(consent_tag_hex="")

    def test_replaced_intake_signature_denied(self):
        self.deny(intake_tag_hex="f" * 64)

    def test_replaced_reviewer_signature_denied(self):
        self.deny(reviewer_tag_hex="f" * 64)

    def test_missing_document_map_denied(self):
        self.deny(trusted_documents=None)

    def test_extra_document_value_denied(self):
        data, _ = self.fixture()
        data["trusted_documents"]["payable_invoice"] = True
        with self.assertRaises(Plan1OrderGateClosed):
            self.run_review(data)

    def test_each_independent_document_cannot_be_substituted(self):
        for field in _DOCUMENT_BINDINGS.values():
            with self.subTest(field=field):
                data, _ = self.fixture()
                data["trusted_documents"][field] = "f" * 64
                with self.assertRaises(Plan1OrderGateClosed):
                    self.run_review(data)

    def test_each_of_twenty_seller_buyer_funding_kyc_gates_stays_closed(self):
        """Twenty independent false facts must fail even if HMAC is recomputed."""
        self.assertEqual(len(REQUIRED), 20)
        for gate in REQUIRED:
            with self.subTest(gate=gate):
                data, _ = self.fixture()
                packet = copy.deepcopy(data["reviewed_packet"])
                packet["facts"][gate] = False
                data["reviewed_packet"] = packet
                data["reviewer_tag_hex"] = sign(packet)
                with self.assertRaises(Plan1OrderGateClosed):
                    self.run_review(data)

    def test_educational_product_packet_denied(self):
        data, _ = self.fixture()
        packet = copy.deepcopy(data["reviewed_packet"])
        packet["sku"] = "MOJPROP-STARTER30"
        data.update(reviewed_packet=packet, reviewer_tag_hex=sign(packet))
        with self.assertRaises(Plan1OrderGateClosed):
            self.run_review(data)

    def test_unpermitted_country_evidence_denied(self):
        data, _ = self.fixture()
        packet = copy.deepcopy(data["reviewed_packet"])
        packet["facts"]["buyer_country_permitted"] = False
        data.update(reviewed_packet=packet, reviewer_tag_hex=sign(packet))
        with self.assertRaises(Plan1OrderGateClosed):
            self.run_review(data)

    def test_unverified_age_evidence_denied(self):
        data, _ = self.fixture()
        packet = copy.deepcopy(data["reviewed_packet"])
        packet["facts"]["buyer_age_verified"] = False
        data.update(reviewed_packet=packet, reviewer_tag_hex=sign(packet))
        with self.assertRaises(Plan1OrderGateClosed):
            self.run_review(data)

    def test_withdrawn_canonical_consent_denied(self):
        data, row = self.fixture()
        row["status"] = "withdrawn"
        with self.assertRaises(Plan1OrderGateClosed):
            self.run_review(data, row=row)

    def test_contacted_canonical_record_requires_new_review(self):
        data, row = self.fixture()
        row["status"] = "contacted"
        with self.assertRaises(Plan1OrderGateClosed):
            self.run_review(data, row=row)

    def test_wrong_consent_version_denied(self):
        data, row = self.fixture()
        row["consent_version"] = "legacy"
        with self.assertRaises(Plan1OrderGateClosed):
            self.run_review(data, row=row)

    def test_wrong_canonical_product_denied(self):
        data, row = self.fixture()
        row["plan_code"] = "MOJPROP-STARTER30"
        with self.assertRaises(Plan1OrderGateClosed):
            self.run_review(data, row=row)

    def test_expired_private_review_denied(self):
        data, _ = self.fixture()
        with self.assertRaises(Plan1OrderGateClosed):
            self.run_review(data, server_now=NOW + 3600)

    def test_future_dated_review_denied(self):
        data, _ = self.fixture()
        with self.assertRaises(Plan1OrderGateClosed):
            self.run_review(data, server_now=NOW - 500)

    def test_consent_to_other_request_cannot_authorize_this_request(self):
        self.deny(request_ref="REQUEST-ZYXWVUTSRQPONMLK")

    def test_private_terms_version_cannot_drift(self):
        data, _ = self.fixture()
        packet = copy.deepcopy(data["reviewed_packet"])
        packet["contract_version"] = "2026-11-14/v1.1"
        data.update(reviewed_packet=packet, reviewer_tag_hex=sign(packet))
        with self.assertRaises(Plan1OrderGateClosed):
            self.run_review(data)

    def test_change_original_intent_does_not_reuse_old_attestations(self):
        data, _ = self.fixture()
        data["inquiry"] = replace(data["inquiry"], declared_country="FR")
        with self.assertRaises(Plan1OrderGateClosed):
            self.run_review(data)
