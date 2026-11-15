"""Guest checkout rejects email parameter pollution before creating an invoice."""
from django.http import QueryDict
from django.test import RequestFactory, SimpleTestCase

from services.mpw_trx_email_recovery import _posted_email


class GuestEmailAmbiguityTests(SimpleTestCase):
    def setUp(self):
        self.rf = RequestFactory()

    def send(self, query):
        return self.rf.post(
            "/commerce/trx-easy/start/72/", data=query,
            content_type="application/x-www-form-urlencoded",
        )

    def test_single_canonical_email_is_accepted(self):
        for key in ("email", "buyer_email", "customer_email",
                    "purchase_email", "purchaser_email"):
            request = self.send(key+"=Buyer%40Example.COM")
            self.assertEqual(_posted_email(request), "buyer@example.com")

    def test_repeated_same_name_even_identical_cannot_confuse_invoice(self):
        for value in ("email=a%40example.org&email=a%40example.org",
                      "buyer_email=a%40example.org&buyer_email="):
            with self.subTest(value=value), self.assertRaises(ValueError):
                _posted_email(self.send(value))

    def test_multiple_aliases_are_not_an_invoice_identity(self):
        cases = (
            "email=a%40example.org&buyer_email=a%40example.org",
            "email=a%40example.org&purchase_email=b%40example.org",
            "email=&buyer_email=a%40example.org",
        )
        for value in cases:
            with self.subTest(value=value), self.assertRaises(ValueError):
                _posted_email(self.send(value))

    def test_missing_and_crlf_injected_email_are_rejected(self):
        for value in ("", "email=%0Aevil%40example.org",
                      "email=a%40example.org%0Abcc%3A%20bad%40example.org"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                _posted_email(self.send(value))
