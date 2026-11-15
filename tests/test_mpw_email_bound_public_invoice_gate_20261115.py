"""Public GET gate enforces buyer email; no payment POST is made."""
from unittest import TestCase
from scripts.mpw_email_bound_public_invoice_gate import has_guarded_guest_email_invoice_form

ACTION=b"/commerce/trx-easy/start/72/"
TOKEN=b"a"*64
FORM=(b'<main><h1>Science of Chess Improvement</h1>'
      b'<form method="post" action="'+ACTION+b'">'
      b'<input type="hidden" name="csrfmiddlewaretoken" value="'+TOKEN+b'">'
      b'<label for="buyer">Email</label>'
      b'<input id="buyer" name="email" type="email" autocomplete="email" '
      b'maxlength="254" required>'
      b'<button type="submit">Create my one-time TRX invoice</button>'
      b'</form></main>')


class PublicEmailBoundInvoiceTests(TestCase):
    def test_valid_buyer_form_accepts_one_email_and_does_not_charge(self):
        self.assertTrue(has_guarded_guest_email_invoice_form(FORM,72))

    def test_missing_email_or_csrf_cannot_pass(self):
        for value in (
            FORM.replace(b'<input id="buyer" name="email" type="email" autocomplete="email" maxlength="254" required>',b''),
            FORM.replace(b'name="csrfmiddlewaretoken"',b'name="csrf_form"'),
            FORM.replace(b'value="'+TOKEN+b'"',b'value=""'),
        ):
            with self.subTest(value=value),self.assertFalse(
                has_guarded_guest_email_invoice_form(value,72))

    def test_ambiguous_or_inert_buyer_email_is_rejected(self):
        for key in (
            b' disabled', b' readonly', b' multiple', b' hidden',
            b' value="other@example.org"', b' type="text"',
            b' name="buyer_email"',
        ):
            # An extra attribute can produce duplicate names: fail closed.
            broken=FORM.replace(b' maxlength="254" required>',key+b' maxlength="254" required>')
            with self.subTest(key=key),self.assertFalse(
                has_guarded_guest_email_invoice_form(broken,72))
        extra=FORM.replace(b'</form>',b'<input name="email" type="email" required></form>')
        self.assertFalse(has_guarded_guest_email_invoice_form(extra,72))

    def test_wrong_invoice_target_or_extra_submit_is_rejected(self):
        for value in (
            FORM.replace(ACTION,b'/commerce/trx-easy/start/225/'),
            FORM.replace(b'method="post"',b'method="get"'),
            FORM.replace(b'</form>',b'<button type="submit">Other</button></form>'),
            FORM.replace(b'</form>',b'</form><form method="post"></form>'),
            FORM.replace(b'<form method=',b'<form onclick="evil()" method='),
        ):
            with self.subTest(value=value),self.assertFalse(
                has_guarded_guest_email_invoice_form(value,72))

    def test_script_and_detached_controls_do_not_pass(self):
        self.assertFalse(has_guarded_guest_email_invoice_form(
            FORM+b'<script>steal()</script>',72))
        self.assertFalse(has_guarded_guest_email_invoice_form(
            FORM+b'<input type="email" name="email">',72))
