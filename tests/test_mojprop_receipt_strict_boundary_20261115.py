"""Strict private Moj Prop receipt identifier/status contract. No real buyers."""
import unittest
from unittest.mock import patch

from django.core import signing
from django.test import SimpleTestCase, override_settings

from core.mojprop_receipts import (
    RECEIPT_AGE_SECONDS, RECEIPT_SALT,
    make_receipt_token, public_status_text,
    valid_request_id, verify_receipt_token,
)

VALID = "MOJPROP-20261115-A1B2C3D4"


@override_settings(SECRET_KEY="private-test-only-mojprop-receipt-signing-secret")
class MojPropStrictReceiptTests(SimpleTestCase):
    def test_canonical_real_request_id_accepted(self):
        self.assertTrue(valid_request_id(VALID))

    def test_receipt_roundtrip_with_real_timestamp_signer(self):
        token = make_receipt_token(VALID)
        self.assertNotEqual(token, VALID)
        self.assertEqual(verify_receipt_token(token), VALID)

    def test_token_does_not_contain_customer_identity(self):
        token = make_receipt_token(VALID)
        self.assertNotIn("@", token)
        self.assertNotIn("buyer", token.lower())

    def test_receipt_cannot_be_forged_with_plain_request_id(self):
        self.assertIsNone(verify_receipt_token(VALID))

    def test_shortened_id_rejected(self):
        with self.assertRaises(ValueError):
            make_receipt_token("MOJPROP-20261115-A1B2C3")

    def test_longer_id_rejected(self):
        with self.assertRaises(ValueError):
            make_receipt_token(VALID + "9")

    def test_wrong_date_segment_rejected(self):
        for value in ("MOJPROP-2026111-A1B2C3D4",
                      "MOJPROP-2026111X-A1B2C3D4"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                make_receipt_token(value)

    def test_lowercase_random_nonce_rejected(self):
        with self.assertRaises(ValueError):
            make_receipt_token("MOJPROP-20261115-a1b2c3d4")

    def test_injected_or_other_prefix_rejected(self):
        for value in ("OTHER-20261115-A1B2C3D4", "MOJPROP-",
                      "MOJPROP-20261115-A1B2C3D4\n",
                      "MOJPROP-20261115-A1B2C3D4/something"):
            with self.subTest(value=repr(value)), self.assertRaises(ValueError):
                make_receipt_token(value)

    def test_nonstring_subclass_is_not_accepted_as_identifier(self):
        class CustomString(str):
            pass
        for value in (None, 1, True, [], CustomString(VALID)):
            with self.subTest(value=repr(value)), self.assertRaises(ValueError):
                make_receipt_token(value)

    def test_cryptographically_valid_but_noncanonical_request_id_is_rejected(self):
        signer = signing.TimestampSigner(salt=RECEIPT_SALT)
        for value in ("MOJPROP-FAKE", "MOJPROP-20261115-a1b2c3d4", "MOJPROP-20261115-FFFFFFFFF"):
            with self.subTest(value=value):
                self.assertIsNone(verify_receipt_token(signer.sign(value)))

    def test_tampered_signature_cannot_track_another_request(self):
        token = make_receipt_token(VALID)
        self.assertIsNone(verify_receipt_token(token[:-1] + ("a" if token[-1] != "a" else "b")))

    def test_multiple_receipts_or_whitespace_are_not_one_credential(self):
        token = make_receipt_token(VALID)
        for invalid in (token + " ", "\n" + token, token + "," + token):
            with self.subTest(value=repr(invalid)):
                self.assertIsNone(verify_receipt_token(invalid))

    def test_token_length_bound_refuses_oversized_content(self):
        self.assertIsNone(verify_receipt_token("a" * 257))

    def test_expired_receipt_does_not_remain_valid(self):
        with patch("django.core.signing.time.time", return_value=1_700_000_000):
            token = make_receipt_token(VALID)
        with patch("django.core.signing.time.time",
                   return_value=1_700_000_000 + RECEIPT_AGE_SECONDS + 1):
            self.assertIsNone(verify_receipt_token(token))

    def test_invalid_token_types_fail_without_exposing_exception(self):
        for value in (None, True, 1, {}, [], b"token"):
            with self.subTest(value=repr(value)):
                self.assertIsNone(verify_receipt_token(value))

    def test_control_and_unicode_surrogates_fail_closed(self):
        token = make_receipt_token(VALID)
        for value in (token + "\x00", token + chr(0xD800), token + chr(0xDFFF)):
            with self.subTest(value=repr(value)):
                self.assertIsNone(verify_receipt_token(value))

    def test_public_status_cannot_claim_settled_money(self):
        for status in ("new", "reviewing", "offer_sent", "approved", "closed"):
            with self.subTest(status=status):
                self.assertNotIn("payment received", public_status_text(status).lower())
                self.assertNotIn("payment confirmed", public_status_text(status).lower())

    def test_delivered_status_is_not_proof_of_customer_receipt(self):
        self.assertIn("independently verify", public_status_text("delivered").lower())

    def test_bad_or_unknown_status_never_leaks_data(self):
        for status in (None, 1, True, [], "billing-paid"):
            with self.subTest(value=repr(status)):
                self.assertEqual(public_status_text(status), "Unavailable")
