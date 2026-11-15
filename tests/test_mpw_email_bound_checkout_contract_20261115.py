"""No-payment checkout HTML validation for buyer-email-owned TRON invoices."""
import unittest
from scripts.mpw_email_bound_checkout_contract_20261115 import (
    has_email_bound_guest_invoice_form as valid,
)


def form(product=72):
    return (
        f'<form method="post" action="/commerce/trx-easy/start/{product}/">'
        '<input type="hidden" name="csrfmiddlewaretoken" value="nonce">'
        '<input type="email" name="email" autocomplete="email" required>'
        '</form>'
    ).encode("utf-8")


class EmailRequiredCheckoutTests(unittest.TestCase):
    def test_one_complete_email_and_csrf_invoice_form(self):
        for product_id in (72, 225, 879):
            with self.subTest(product_id=product_id):
                self.assertTrue(valid(form(product_id), product_id))

    def test_missing_buyer_email_is_never_authorized(self):
        self.assertFalse(valid(form().replace(
            b'<input type="email" name="email" autocomplete="email" required>', b""
        ), 72))

    def test_email_must_be_submitted_blank_required_and_correctly_typed(self):
        for replacement in (
            b'<input type="text" name="email" required>',
            b'<input type="email" name="buyer" required>',
            b'<input type="email" name="email">',
            b'<input type="email" name="email" required disabled>',
            b'<input type="email" name="email" value="buyer@example.com" required>',
            b'<input type="hidden" name="email" required>',
            b'<input type="email" name="email" required name="other">',
        ):
            with self.subTest(replacement=replacement):
                original = b'<input type="email" name="email" autocomplete="email" required>'
                self.assertFalse(valid(form().replace(original, replacement), 72))

    def test_csrf_required_hidden_unique_and_submitted(self):
        original = b'<input type="hidden" name="csrfmiddlewaretoken" value="nonce">'
        for replacement in (
            b'', b'<input type="hidden" name="csrfmiddlewaretoken" value="">',
            b'<input name="csrfmiddlewaretoken" value="nonce">',
            b'<input type="hidden" name="csrfmiddlewaretoken" value="nonce" disabled>',
            original + original,
        ):
            with self.subTest(replacement=replacement):
                self.assertFalse(valid(form().replace(original, replacement), 72))

    def test_wrong_action_or_method_and_duplicate_target_form_fail(self):
        self.assertFalse(valid(form().replace(b'method="post"', b'method="get"'), 72))
        self.assertFalse(valid(form().replace(b'/start/72/', b'/start/879/'), 72))
        self.assertFalse(valid(form() + form(), 72))

    def test_detached_or_secondary_email_collection_is_not_a_valid_single_owner(self):
        for extra in (
            b'<input type="email" name="email" required>',
            b'<form><input type="email" name="email"></form>',
            b'<form><input name="buyer_email" type="text"></form>',
            b'<input name="e&#109;ail" type="text">',
            b'<input type="em&amp;#97;il" name="contact">',
        ):
            with self.subTest(extra=extra):
                self.assertFalse(valid(form() + extra, 72))

    def test_missing_form_close_and_malformed_utf8_are_denied(self):
        self.assertFalse(valid(form()[:-7], 72))
        self.assertFalse(valid(b"\xff\xfe", 72))
        self.assertFalse(valid(form(), "72"))
        self.assertFalse(valid(form(), True))


if __name__ == "__main__":
    unittest.main()
