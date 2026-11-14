"""Adversarial browser-visibility checks for MojPlayWin guest email checkout.

These are real parsing tests, not any buyer purchase, wallet transfer or render on live cPanel.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "services/mpw_checkout_render_contract.py"
spec = importlib.util.spec_from_file_location("mpw_checkout_inert_review", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

CSRF = '<input type="hidden" name="csrfmiddlewaretoken" value="' + 'A'*64 + '">'
EMAIL = '<input type="email" name="email" required maxlength="254" autocomplete="email">'
BUTTON = '<button type="submit">Create TRX invoice</button>'
FORM_START = '<form method="post" action="/commerce/trx-easy/start/72/">'
MAIN_END = '</main>'
VISIBLE = "rendered_form_structurally_valid_not_paid"
BLOCKED = "checkout_active_or_ambiguous_markup"


def page():
    return ('<!doctype html><html><head><title>MojPlayWin</title></head>'
            '<body><main>' + FORM_START + CSRF + EMAIL + BUTTON
            + '</form></main></body></html>')


class Response:
    status_code = 200
    streaming = False
    def __init__(self, html=None):
        self.content = (html if html is not None else page()).encode("utf-8")


class InertControlCases(unittest.TestCase):
    def verdict(self, html):
        return mod.checkout_markup_category(Response(html), 72)

    def wrap(self, snippet, before, after):
        self.assertIn(snippet, page())
        return page().replace(snippet, before + snippet + after)

    def test_01_existing_checkout_still_accepted_as_not_paid(self):
        self.assertEqual(self.verdict(page()), VISIBLE)

    def test_02_email_in_disabled_fieldset_is_not_submittable(self):
        self.assertEqual(self.verdict(self.wrap(EMAIL, "<fieldset disabled>", "</fieldset>")), BLOCKED)

    def test_03_csrf_in_disabled_fieldset_never_validates(self):
        self.assertEqual(self.verdict(self.wrap(CSRF, "<fieldset disabled>", "</fieldset>")), BLOCKED)

    def test_04_submit_inside_disabled_fieldset_cannot_start_invoice(self):
        self.assertEqual(self.verdict(self.wrap(BUTTON, "<fieldset disabled>", "</fieldset>")), BLOCKED)

    def test_05_outer_disabled_fieldset_around_entire_form_is_blocked(self):
        self.assertEqual(self.verdict(self.wrap(FORM_START + CSRF + EMAIL + BUTTON + "</form>",
                                             "<fieldset disabled>", "</fieldset>")), BLOCKED)

    def test_06_form_inside_html_hidden_container_not_usable(self):
        self.assertEqual(self.verdict(page().replace("<main>", "<main><div hidden>").replace(
            MAIN_END, "</div>" + MAIN_END)), BLOCKED)

    def test_07_form_inside_inert_container_not_usable(self):
        self.assertEqual(self.verdict(page().replace("<main>", "<main><section inert>").replace(
            MAIN_END, "</section>" + MAIN_END)), BLOCKED)

    def test_08_aria_hidden_true_ancestor_blocks_checkout(self):
        self.assertEqual(self.verdict(page().replace("<main>", '<main><div aria-hidden="true">').replace(
            MAIN_END, "</div>" + MAIN_END)), BLOCKED)

    def test_09_aria_disabled_true_ancestor_blocks_checkout(self):
        self.assertEqual(self.verdict(page().replace("<main>", '<main><div aria-disabled="true">').replace(
            MAIN_END, "</div>" + MAIN_END)), BLOCKED)

    def test_10_hidden_email_field_cannot_collect_buyer_address(self):
        self.assertEqual(self.verdict(page().replace(EMAIL, EMAIL[:-1] + " hidden>")), BLOCKED)

    def test_11_inert_email_field_cannot_collect_buyer_address(self):
        self.assertEqual(self.verdict(page().replace(EMAIL, EMAIL[:-1] + " inert>")), BLOCKED)

    def test_12_aria_hidden_email_field_not_proof_of_usable_contact(self):
        self.assertEqual(self.verdict(page().replace(EMAIL, EMAIL[:-1] + ' aria-hidden="true">')), BLOCKED)

    def test_13_aria_disabled_email_field_not_usable(self):
        self.assertEqual(self.verdict(page().replace(EMAIL, EMAIL[:-1] + ' aria-disabled="true">')), BLOCKED)

    def test_14_css_display_none_email_not_usable(self):
        self.assertEqual(self.verdict(page().replace(EMAIL, EMAIL[:-1] + ' style="display: none">')), BLOCKED)

    def test_15_css_visibility_hidden_email_not_usable(self):
        self.assertEqual(self.verdict(page().replace(EMAIL, EMAIL[:-1] + ' style="visibility: hidden">')), BLOCKED)

    def test_16_css_content_visibility_hidden_email_not_usable(self):
        self.assertEqual(self.verdict(page().replace(EMAIL, EMAIL[:-1] + ' style="content-visibility: hidden">')), BLOCKED)

    def test_17_css_opacity_zero_email_not_usable(self):
        self.assertEqual(self.verdict(page().replace(EMAIL, EMAIL[:-1] + ' style="opacity: 0">')), BLOCKED)

    def test_18_css_pointer_events_none_email_not_usable(self):
        self.assertEqual(self.verdict(page().replace(EMAIL, EMAIL[:-1] + ' style="pointer-events: none">')), BLOCKED)

    def test_19_submit_with_css_display_none_cannot_certify_buy_path(self):
        self.assertEqual(self.verdict(page().replace(BUTTON, '<button style="display: none" type="submit">Pay</button>')), BLOCKED)

    def test_20_submit_with_aria_hidden_true_not_accessible(self):
        self.assertEqual(self.verdict(page().replace(BUTTON, '<button type="submit" aria-hidden="true">Pay</button>')), BLOCKED)

    def test_21_submit_with_inert_attribute_not_usable(self):
        self.assertEqual(self.verdict(page().replace(BUTTON, '<button type="submit" inert>Pay</button>')), BLOCKED)

    def test_22_form_hidden_itself_is_blocking(self):
        self.assertEqual(self.verdict(page().replace(FORM_START, FORM_START[:-1] + ' hidden>')), BLOCKED)

    def test_23_form_style_display_none_is_blocking(self):
        self.assertEqual(self.verdict(page().replace(FORM_START, FORM_START[:-1] + ' style="display: none">')), BLOCKED)

    def test_24_checkout_inside_closed_dialog_cannot_start_invoice(self):
        self.assertEqual(self.verdict(page().replace("<main>", "<main><dialog>").replace(MAIN_END, "</dialog>" + MAIN_END)), BLOCKED)

    def test_25_checkout_inside_template_inert_fragment_not_real_form(self):
        self.assertEqual(self.verdict(page().replace("<main>", "<main><template>").replace(MAIN_END, "</template>" + MAIN_END)), BLOCKED)

    def test_26_checkout_inside_closed_details_inert(self):
        self.assertEqual(self.verdict(page().replace("<main>", "<main><details>").replace(MAIN_END, "</details>" + MAIN_END)), BLOCKED)

    def test_27_nested_hidden_container_never_loses_scope_early(self):
        html = page().replace(EMAIL, '<div hidden><span><em>' + EMAIL + '</em></span></div>')
        self.assertEqual(self.verdict(html), BLOCKED)

    def test_28_minlength_beyond_maxlength_unusable(self):
        self.assertEqual(self.verdict(page().replace(EMAIL, EMAIL[:-1] + ' minlength="255">')), BLOCKED)

    def test_29_negative_minlength_is_invalid(self):
        self.assertEqual(self.verdict(page().replace(EMAIL, EMAIL[:-1] + ' minlength="-1">')), BLOCKED)

    def test_30_malformed_minlength_is_invalid(self):
        self.assertEqual(self.verdict(page().replace(EMAIL, EMAIL[:-1] + ' minlength="not-an-int">')), BLOCKED)

    def test_31_duplicate_maxlength_must_be_rejected(self):
        self.assertEqual(self.verdict(page().replace(EMAIL, EMAIL[:-1] + ' maxlength="5">')), BLOCKED)

    def test_32_duplicate_minlength_must_be_rejected(self):
        self.assertEqual(self.verdict(page().replace(EMAIL, EMAIL[:-1] + ' minlength="2" minlength="7">')), BLOCKED)

    def test_33_custom_pattern_may_block_valid_email(self):
        self.assertEqual(self.verdict(page().replace(EMAIL, EMAIL[:-1] + ' pattern="nevermatch">')), BLOCKED)

    def test_34_no_keyboard_inputmode_blocks_mobile_checkout(self):
        self.assertEqual(self.verdict(page().replace(EMAIL, EMAIL[:-1] + ' inputmode="none">')), BLOCKED)

    def test_35_visible_email_can_still_be_used_after_closed_hidden_wrapper(self):
        html = page().replace(EMAIL, '<div hidden><p>marketing</p></div>' + EMAIL)
        self.assertEqual(self.verdict(html), VISIBLE)

    def test_36_unrelated_disabled_optional_fieldset_does_not_block_buyer(self):
        html = page().replace(BUTTON,
            '<fieldset disabled><input type="text" name="optional_coupon" value="X"></fieldset>' + BUTTON)
        self.assertEqual(self.verdict(html), VISIBLE)

    def test_37_open_dialog_with_visible_form_is_usable(self):
        html = page().replace("<main>", "<main><dialog open>").replace(
            MAIN_END, "</dialog>" + MAIN_END)
        self.assertEqual(self.verdict(html), VISIBLE)

    def test_38_open_details_with_visible_form_is_usable(self):
        html = page().replace("<main>", "<main><details open>").replace(
            MAIN_END, "</details>" + MAIN_END)
        self.assertEqual(self.verdict(html), VISIBLE)

    def test_39_aria_hidden_false_does_not_imply_inert(self):
        self.assertEqual(self.verdict(page().replace(EMAIL, EMAIL[:-1] + ' aria-hidden="false">')), VISIBLE)

    def test_40_email_minlength_at_six_allowed(self):
        self.assertEqual(self.verdict(page().replace(EMAIL, EMAIL[:-1] + ' minlength="6">')), VISIBLE)

    def test_41_html_comment_hidden_markup_is_not_active_form(self):
        html = page().replace("</main>", "<!-- <fieldset disabled>"+EMAIL+"</fieldset> --></main>")
        self.assertEqual(self.verdict(html), VISIBLE)

    def test_42_password_field_cannot_satisfy_email_rule(self):
        self.assertNotEqual(self.verdict(page().replace('type="email"','type="password"')), VISIBLE)

    def test_43_no_customer_data_or_payment_in_contract_module(self):
        text = MODULE_PATH.read_text(encoding="utf-8")
        for banned in ("requests.get(", "urllib.request", "send_mail(", "send_transaction("):
            self.assertNotIn(banned, text)


if __name__ == "__main__":
    unittest.main()
