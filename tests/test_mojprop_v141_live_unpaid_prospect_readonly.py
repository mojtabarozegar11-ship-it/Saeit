"""Synthetic adversarial tests for public read-only mainline prospect verification."""
import unittest

from scripts.mojprop_v141_live_unpaid_prospect_readonly import classify


FORM = """<!doctype html><html><body>
<p>Prelaunch interest only: MOJ-PROP-01: 30 TRX not payable</p>
<form method="post" action="/moj-prop-intake/?format=html">
<input type="hidden" name="csrfmiddlewaretoken" value="demo-token">
<input type="text" name="name" required>
<input type="email" name="email" required>
<select name="service"><option value="blueprint">blueprint</option></select>
<select name="horizon"><option value="30-days">30</option></select>
<textarea name="notes">Prelaunch interest only: MOJ-PROP-01</textarea>
<input type="hidden" name="website" value="">
<input type="hidden" name="idempotency_key" value="123e4567-e89b-42d3-a456-426614174000">
<input type="checkbox" name="consent" required value="on">
<button type="submit">Submit</button></form></body></html>"""

STATUS = """<!doctype html><html><body><form method="post"
action="/moj-prop-status/?format=html">
<input type="hidden" name="csrfmiddlewaretoken" value="demo-token">
<input name="receipt_token" required><button type="submit">Lookup</button>
</form></body></html>"""


class UnpaidProspectReadOnlyTests(unittest.TestCase):
    def review(self, source=FORM, route="prelaunch_moj_prop_01", code=200):
        return classify(status=code,raw=source.encode(),route=route)

    def test_01_valid_prelaunch_html_get_is_not_a_paid_order(self):
        result=self.review()
        self.assertTrue(result["nonpayable_form_get_valid"])
        self.assertFalse(result["payment_created"])
        self.assertFalse(result["submitted"])

    def test_02_404_is_a_blocked_lead_form(self):
        self.assertFalse(self.review(code=404)["nonpayable_form_get_valid"])

    def test_03_blank_csrf_is_not_a_real_safe_form(self):
        self.assertFalse(self.review(FORM.replace('value="demo-token"','value=""'))["csrf_present"])

    def test_04_fake_form_comment_does_not_validate(self):
        self.assertFalse(self.review("<!--"+FORM+"-->")["nonpayable_form_get_valid"])

    def test_05_external_post_action_rejected(self):
        self.assertFalse(self.review(FORM.replace('action="/moj-prop-intake/?format=html"','action="https://attacker.example/"'))["nonpayable_form_get_valid"])

    def test_06_malformed_unclosed_form_rejected(self):
        self.assertFalse(self.review(FORM.replace("</form>",""))["nonpayable_form_get_valid"])

    def test_07_extra_wallet_key_input_rejected(self):
        corrupt=FORM.replace("<button type=", '<input type="text" name="private_key"><button type=')
        self.assertFalse(self.review(corrupt)["nonpayable_form_get_valid"])

    def test_08_script_or_iframe_rejected(self):
        self.assertFalse(self.review(FORM.replace("</body>","<script>0</script></body>"))["nonpayable_form_get_valid"])
        self.assertFalse(self.review(FORM.replace("</body>","<iframe></iframe></body>"))["nonpayable_form_get_valid"])

    def test_09_untrusted_missing_challenge_terms_rejected(self):
        self.assertFalse(self.review(FORM.replace("not payable","pay now"))["nonpayable_form_get_valid"])

    def test_10_receipt_lookup_does_not_prove_a_buyer_created(self):
        result=self.review(STATUS,route="manual_review_status")
        self.assertTrue(result["nonpayable_form_get_valid"])
        self.assertTrue(result["receipt_proof_present"])
        self.assertFalse(result["submitted"])

    def test_11_receipt_token_on_get_url_is_not_part_of_expected_form(self):
        bad=STATUS.replace('name="receipt_token"','name="request_id"')
        self.assertFalse(self.review(bad,route="manual_review_status")["nonpayable_form_get_valid"])

    def test_12_oversize_http_body_cannot_be_authenticated_as_a_form(self):
        big=FORM+"X"*66000
        self.assertFalse(self.review(big)["nonpayable_form_get_valid"])

    def test_13_json_status_is_not_html_form(self):
        self.assertFalse(self.review('{"ok":true}',route="manual_review_status")["nonpayable_form_get_valid"])

if __name__ == "__main__":
    unittest.main()
