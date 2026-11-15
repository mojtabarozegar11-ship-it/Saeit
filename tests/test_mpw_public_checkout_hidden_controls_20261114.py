"""Actual public observer classification must not accept unreachable buyer controls."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/mpw_onepass_public_sales_audit_20261113.py"
spec = importlib.util.spec_from_file_location("mpw_public_inert_audit", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

EMAIL = '<input type="email" name="email" required maxlength="254" autocomplete="email">'
CSRF = '<input name="csrfmiddlewaretoken" type="hidden" value="' + "A"*64 + '">'
BUTTON = '<button type="submit">Create invoice</button>'
FORM = '<form action="/commerce/trx-easy/start/72/" method="post">'
VALID = "buyer_email_input_get_ok_not_paid"
NO_FORM = "checkout_post_action_unverified"


def html():
    return ("<!doctype html><html><head><title>MojPlayWin checkout</title></head>"
            "<body><main>" + FORM + CSRF + EMAIL + BUTTON +
            "</form></main></body></html>")


class ReadOnlyFormReality(unittest.TestCase):
    def verdict(self, value):
        return mod.classify_html("checkout", 72, value)

    def test_01_visible_guest_email_post_has_get_only_category(self):
        self.assertEqual(self.verdict(html()), VALID)

    def test_02_hidden_main_disqualifies_form(self):
        self.assertEqual(self.verdict(html().replace("<main>", "<main hidden>")), NO_FORM)

    def test_03_inert_main_disqualifies_form(self):
        self.assertEqual(self.verdict(html().replace("<main>", "<main inert>")), NO_FORM)

    def test_04_disabled_fieldset_disqualifies_email(self):
        self.assertEqual(self.verdict(html().replace(EMAIL, "<fieldset disabled>"+EMAIL+"</fieldset>")), NO_FORM)

    def test_05_disabled_fieldset_disqualifies_csrf(self):
        self.assertEqual(self.verdict(html().replace(CSRF, "<fieldset disabled>"+CSRF+"</fieldset>")), NO_FORM)

    def test_06_disabled_fieldset_disqualifies_button(self):
        self.assertEqual(self.verdict(html().replace(BUTTON, "<fieldset disabled>"+BUTTON+"</fieldset>")), NO_FORM)

    def test_07_template_form_is_not_browser_checkout(self):
        self.assertEqual(self.verdict(html().replace("<main>", "<main><template>").replace("</main>", "</template></main>")), NO_FORM)

    def test_08_closed_dialog_form_is_not_browser_checkout(self):
        self.assertEqual(self.verdict(html().replace("<main>", "<main><dialog>").replace("</main>", "</dialog></main>")), NO_FORM)

    def test_09_closed_details_form_is_not_browser_checkout(self):
        self.assertEqual(self.verdict(html().replace("<main>", "<main><details>").replace("</main>", "</details></main>")), NO_FORM)

    def test_10_inline_display_none_email_unusable(self):
        self.assertEqual(self.verdict(html().replace(EMAIL, EMAIL[:-1]+' style="display: none">')), NO_FORM)

    def test_11_inline_visibility_hidden_email_unusable(self):
        self.assertEqual(self.verdict(html().replace(EMAIL, EMAIL[:-1]+' style="visibility: hidden">')), NO_FORM)

    def test_12_inline_opacity_zero_email_unusable(self):
        self.assertEqual(self.verdict(html().replace(EMAIL, EMAIL[:-1]+' style="opacity: 0">')), NO_FORM)

    def test_13_inline_pointer_events_none_email_unusable(self):
        self.assertEqual(self.verdict(html().replace(EMAIL, EMAIL[:-1]+' style="pointer-events: none">')), NO_FORM)

    def test_14_inline_content_visibility_hidden_email_unusable(self):
        self.assertEqual(self.verdict(html().replace(EMAIL, EMAIL[:-1]+' style="content-visibility: hidden">')), NO_FORM)

    def test_15_email_aria_hidden_unusable(self):
        self.assertEqual(self.verdict(html().replace(EMAIL, EMAIL[:-1]+' aria-hidden="true">')), NO_FORM)

    def test_16_email_aria_disabled_unusable(self):
        self.assertEqual(self.verdict(html().replace(EMAIL, EMAIL[:-1]+' aria-disabled="true">')), NO_FORM)

    def test_17_email_hidden_unusable(self):
        self.assertEqual(self.verdict(html().replace(EMAIL, EMAIL[:-1]+' hidden>')), NO_FORM)

    def test_18_submit_css_hidden_unusable(self):
        self.assertEqual(self.verdict(html().replace(BUTTON, '<button type="submit" style="display:none">Pay</button>')), NO_FORM)

    def test_19_submit_inert_unusable(self):
        self.assertEqual(self.verdict(html().replace(BUTTON, '<button type="submit" inert>Pay</button>')), NO_FORM)

    def test_20_email_pattern_cannot_arbitrarily_reject_address(self):
        self.assertEqual(self.verdict(html().replace(EMAIL, EMAIL[:-1]+' pattern="no-email-ever">')), NO_FORM)

    def test_21_email_inputmode_none_blocks_mobile(self):
        self.assertEqual(self.verdict(html().replace(EMAIL, EMAIL[:-1]+' inputmode="none">')), NO_FORM)

    def test_22_email_minlength_too_long_blocks(self):
        self.assertEqual(self.verdict(html().replace(EMAIL, EMAIL[:-1]+' minlength="255">')), NO_FORM)

    def test_23_duplicate_maxlength_blocks(self):
        self.assertEqual(self.verdict(html().replace(EMAIL, EMAIL[:-1]+' maxlength="1">')), NO_FORM)

    def test_24_duplicate_minlength_blocks(self):
        self.assertEqual(self.verdict(html().replace(EMAIL, EMAIL[:-1]+' minlength="3" minlength="4">')), NO_FORM)

    def test_25_outer_hidden_container_blocks_while_inner_is_closed(self):
        self.assertEqual(self.verdict(html().replace(EMAIL,
            '<div hidden><span><i>'+EMAIL+'</i></span></div>')), NO_FORM)

    def test_26_closed_hidden_wrapper_does_not_disable_later_contact(self):
        value = html().replace(EMAIL, '<div hidden><p>Promotion</p></div>'+EMAIL)
        self.assertEqual(self.verdict(value), VALID)

    def test_27_unrelated_disabled_coupon_does_not_block_buyer(self):
        value = html().replace(EMAIL, EMAIL + '<fieldset disabled><input name="coupon"></fieldset>')
        self.assertEqual(self.verdict(value), VALID)

    def test_28_open_dialog_form_remains_visible(self):
        value = html().replace("<main>", "<main><dialog open>").replace("</main>", "</dialog></main>")
        self.assertEqual(self.verdict(value), VALID)

    def test_29_open_details_form_remains_visible(self):
        value = html().replace("<main>", "<main><details open>").replace("</main>", "</details></main>")
        self.assertEqual(self.verdict(value), VALID)

    def test_30_existing_required_email_cannot_be_removed(self):
        self.assertEqual(self.verdict(html().replace("required maxlength", "maxlength")),
                         "buyer_email_input_unverified")

    def test_31_duplicate_email_fields_remain_unverified(self):
        self.assertEqual(self.verdict(html().replace(EMAIL, EMAIL + EMAIL)),
                         "buyer_email_input_unverified")

    def test_32_post_action_remains_exact_local_route(self):
        self.assertEqual(self.verdict(html().replace("/start/72/", "/start/225/")),
                         NO_FORM)

    def test_33_parser_and_readonly_classification_never_proves_payment(self):
        self.assertIn("not_paid", self.verdict(html()))

    def test_34_module_does_not_send_payments_or_customer_emails(self):
        s = SCRIPT.read_text("utf8")
        for token in ("requests.post(", "send_mail(", "transact(", "payment_intent.create("):
            self.assertNotIn(token, s)


if __name__ == "__main__":
    unittest.main()
