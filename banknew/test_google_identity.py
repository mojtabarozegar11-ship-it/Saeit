"""MOJ Pay Google OIDC checks use mocked verified claims, not real credentials."""
import unittest
from unittest.mock import patch

from banknew.google_identity import (
    GoogleIdentityError, GoogleIdentityUnavailable, GooglePrincipal,
    generate_server_nonce, verify_google_credential,
)

CLIENT = "123456789-abcdef0123456789.apps.googleusercontent.com"
NONCE = "A" * 32
CREDENTIAL = "header.payload.signature"


def claims(**updates):
    payload = {
        "sub": "109876543210987654321",
        "iss": "https://accounts.google.com",
        "aud": CLIENT,
        "nonce": NONCE,
        "iat": 1900,
        "exp": 2100,
        "email": "person@gmail.com",
        "email_verified": True,
    }
    payload.update(updates)
    return payload


def verify(payload=None):
    with patch("banknew.google_identity.time.time", return_value=2000), patch(
        "banknew.google_identity._google_verify", return_value=(
            claims() if payload is None else payload
        )
    ) as cryptographic:
        principal = verify_google_credential(
            CREDENTIAL, client_id=CLIENT, expected_nonce=NONCE
        )
        cryptographic.assert_called_once_with(CREDENTIAL, CLIENT)
        return principal


class GoogleIdentityTests(unittest.TestCase):
    def test_valid_signed_claims_return_stable_subject_not_email_key(self):
        principal = verify()
        self.assertIsInstance(principal, GooglePrincipal)
        self.assertEqual(principal.subject, "109876543210987654321")
        self.assertEqual(principal.email, "person@gmail.com")
        self.assertIsNone(principal.hosted_domain)
        self.assertFalse(principal.financial_kyc_verified)

    def test_valid_workspace_domain_is_optional_metadata(self):
        self.assertEqual(verify(claims(hd="example.com")).hosted_domain, "example.com")

    def test_random_nonce_uses_secure_urlsafe_entropy(self):
        a, b = generate_server_nonce(), generate_server_nonce()
        self.assertNotEqual(a, b)
        self.assertGreaterEqual(len(a), 32)
        self.assertTrue(all(x.isalnum() or x in "-_" for x in a))

    def test_wrong_nonce_missing_nonce_and_replay_rejected(self):
        for payload in (claims(nonce="B" * 32), claims(nonce=None),
                        claims(nonce=""), claims(nonce=NONCE + "x")):
            with self.subTest(payload=payload["nonce"]), self.assertRaisesRegex(
                GoogleIdentityError, "replay"
            ):
                verify(payload)

    def test_wrong_audience_issuer_or_authorized_party_rejected(self):
        for payload in (claims(aud="other.apps.googleusercontent.com"),
                        claims(iss="https://malicious.example"),
                        claims(azp="different-client"),
                        claims(iss="http://accounts.google.com")):
            with self.subTest(payload=payload), self.assertRaises(GoogleIdentityError):
                verify(payload)

    def test_expiry_and_future_issue_time_rejected(self):
        for payload in (
            claims(exp=2000), claims(exp=1000),
            claims(exp="2100"), claims(iat=2200),
            claims(iat=True), claims(exp=True), claims(iat=2100, exp=1900)
        ):
            with self.subTest(payload=payload), self.assertRaises(GoogleIdentityError):
                verify(payload)

    def test_email_verification_must_be_exact_boolean_true(self):
        for value in (False, None, "true", 1, "True"):
            with self.subTest(value=value), self.assertRaises(GoogleIdentityError):
                verify(claims(email_verified=value))

    def test_invalid_subject_email_and_hosted_domain_rejected(self):
        for payload in (
            claims(sub=""), claims(sub="x"),
            claims(email="personexample.com"), claims(email=" \n"),
            claims(email="bob@gmail.com\n"), claims(hd="\nmalicious")
        ):
            with self.subTest(payload=payload), self.assertRaises(GoogleIdentityError):
                verify(payload)

    def test_missing_client_nonce_and_malformed_token_fail_before_crypto(self):
        for credentials, client, nonce in (
            (CREDENTIAL, "", NONCE),
            (CREDENTIAL, "http://localhost", NONCE),
            (CREDENTIAL, CLIENT, ""),
            (CREDENTIAL, CLIENT, "short"),
            ("not-a-jwt", CLIENT, NONCE),
            ("header.payload.signature." + "x" * 20000, CLIENT, NONCE),
        ):
            with patch("banknew.google_identity._google_verify") as cryptographic:
                with self.assertRaises(GoogleIdentityError):
                    verify_google_credential(
                        credentials, client_id=client, expected_nonce=nonce
                    )
                cryptographic.assert_not_called()

    def test_crypto_validation_failure_does_not_echo_token(self):
        with patch("banknew.google_identity._google_verify",
                   side_effect=ValueError("raw provider internals")):
            with self.assertRaises(GoogleIdentityError) as error:
                verify_google_credential(
                    CREDENTIAL, client_id=CLIENT, expected_nonce=NONCE
                )
        self.assertNotIn(CREDENTIAL, str(error.exception))
        self.assertNotIn("provider internals", str(error.exception))

    def test_missing_crypto_library_fails_closed(self):
        with patch("banknew.google_identity._google_verify",
                   side_effect=ImportError("google-auth missing")):
            with self.assertRaises(GoogleIdentityUnavailable):
                verify_google_credential(
                    CREDENTIAL, client_id=CLIENT, expected_nonce=NONCE
                )

    def test_untrusted_dict_is_not_accepted_instead_of_jwt(self):
        with self.assertRaises(GoogleIdentityError):
            verify_google_credential(
                {"sub": "109876543210987654321"},
                client_id=CLIENT, expected_nonce=NONCE
            )


if __name__ == "__main__":
    unittest.main()
