"""Adversarial, offline contracts for the exact rendered TRX checkout.

No Django runtime, customer data, server calls, invoice creation, email or payment.
"""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "services/mpw_checkout_render_contract.py"
spec = importlib.util.spec_from_file_location("mpw_rendered_checkout_contract", SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

TOKEN = "A" * 64
EMAIL = '<input type="email" name="email" required maxlength="254" autocomplete="email">'
CSRF = '<input type="hidden" name="csrfmiddlewaretoken" value="' + TOKEN + '">'
BUTTON = '<button type="submit">Create TRX invoice</button>'


def page(sku=72):
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<title>MojPlayWin checkout</title></head><body><main>'
            f'<form method="post" action="/commerce/trx-easy/start/{sku}/">'
            + CSRF + EMAIL + BUTTON + '</form></main></body></html>')


class Response:
    status_code = 200
    streaming = False

    def __init__(self, html=None, *, code=200, stream=False, raw=None):
        self.content = (html if html is not None else page()).encode("utf-8") if raw is None else raw
        self.status_code = code
        self.streaming = stream


class CheckoutRenderContractTests(unittest.TestCase):
    def category(self, html=None, *, sku=72, **options):
        return module.checkout_markup_category(Response(html, **options), sku)

    def edited(self, old, new="", *, sku=72):
        self.assertIn(old, page(sku))
        return self.category(page(sku).replace(old, new), sku=sku)

    def test_01_valid_checkout_is_structural_not_sales_proof(self):
        self.assertEqual(self.category(), "rendered_form_structurally_valid_not_paid")

    def test_02_valid_32_character_django_csrf_token(self):
        self.assertEqual(self.edited(TOKEN, "B"*32),
                         "rendered_form_structurally_valid_not_paid")

    def test_03_product_id_must_match_exact_order_post(self):
        self.assertEqual(self.category(page(72), sku=225),
                         "checkout_active_or_ambiguous_markup")

    def test_04_boolean_product_id_is_invalid_not_integer(self):
        self.assertEqual(self.category(sku=True), "invalid_product")

    def test_05_zero_product_id_is_invalid(self):
        self.assertEqual(self.category(sku=0), "invalid_product")

    def test_06_non_200_response_cannot_be_served_as_checkout(self):
        self.assertEqual(self.category(code=503), "response_not_rendered_html")

    def test_07_streaming_response_cannot_be_verified(self):
        self.assertEqual(self.category(stream=True), "response_not_rendered_html")

    def test_08_tiny_error_page_is_not_a_real_checkout(self):
        self.assertEqual(self.category(raw=b"<h1>Error</h1>"),
                         "checkout_body_unreadable")

    def test_09_body_exceeding_bounded_size_fails_closed(self):
        self.assertEqual(self.category(raw=b"x"*(module.MAX_CHECKOUT_BYTES+1)),
                         "checkout_body_unreadable")

    def test_10_invalid_utf8_never_passes(self):
        self.assertEqual(self.category(raw=b"\xff"*200),
                         "checkout_body_unreadable")

    def test_11_non_bytes_body_never_passes(self):
        response = Response()
        response.content = "A" * 300
        self.assertEqual(module.checkout_markup_category(response, 72),
                         "checkout_body_unreadable")

    def test_12_missing_email_is_blocking(self):
        self.assertEqual(self.edited(EMAIL), "checkout_buyer_email_unverified")

    def test_13_optional_email_does_not_qualify(self):
        self.assertEqual(self.edited(" required maxlength=", " maxlength="),
                         "checkout_buyer_email_unverified")

    def test_14_disabled_email_does_not_qualify(self):
        self.assertEqual(self.edited("name=\"email\" required", "name=\"email\" required disabled"),
                         "checkout_buyer_email_unverified")

    def test_15_readonly_email_does_not_qualify(self):
        self.assertEqual(self.edited("name=\"email\" required", "name=\"email\" required readonly"),
                         "checkout_buyer_email_unverified")

    def test_16_multiple_addresses_are_not_one_buyer(self):
        self.assertEqual(self.edited("name=\"email\" required", "name=\"email\" required multiple"),
                         "checkout_buyer_email_unverified")

    def test_17_text_input_cannot_masquerade_as_email(self):
        self.assertEqual(self.edited('type="email"', 'type="text"'),
                         "checkout_buyer_email_unverified")

    def test_18_unknown_email_field_name_rejected(self):
        self.assertEqual(self.edited('name="email"', 'name="contact"'),
                         "checkout_buyer_email_unverified")

    def test_19_two_buyer_contacts_are_ambiguous(self):
        self.assertEqual(self.edited(EMAIL, EMAIL+EMAIL),
                         "checkout_buyer_email_unverified")

    def test_20_email_maxlength_below_minimum_is_invalid(self):
        self.assertEqual(self.edited('maxlength="254"', 'maxlength="4"'),
                         "checkout_active_or_ambiguous_markup")

    def test_21_email_maxlength_above_254_is_invalid(self):
        self.assertEqual(self.edited('maxlength="254"', 'maxlength="999"'),
                         "checkout_active_or_ambiguous_markup")

    def test_22_email_maxlength_malformed_is_invalid(self):
        self.assertEqual(self.edited('maxlength="254"', 'maxlength="four"'),
                         "checkout_active_or_ambiguous_markup")

    def test_23_missing_csrf_is_blocking(self):
        self.assertEqual(self.edited(CSRF), "checkout_csrf_unverified")

    def test_24_csrf_must_be_hidden(self):
        self.assertEqual(self.edited('type="hidden"', 'type="text"'),
                         "checkout_csrf_unverified")

    def test_25_csrf_short_token_rejected(self):
        self.assertEqual(self.edited(TOKEN, "not-a-valid-token"),
                         "checkout_csrf_unverified")

    def test_26_non_alphanumeric_csrf_rejected(self):
        self.assertEqual(self.edited(TOKEN, "B"*63+"-"),
                         "checkout_csrf_unverified")

    def test_27_disabled_csrf_rejected(self):
        self.assertEqual(self.edited('name="csrfmiddlewaretoken"',
                                     'name="csrfmiddlewaretoken" disabled'),
                         "checkout_csrf_unverified")

    def test_28_duplicate_csrf_rejected(self):
        self.assertEqual(self.edited(CSRF, CSRF+CSRF),
                         "checkout_csrf_unverified")

    def test_29_missing_submit_control_rejected(self):
        self.assertEqual(self.edited(BUTTON), "checkout_submit_unverified")

    def test_30_disabled_submit_control_rejected(self):
        self.assertEqual(self.edited('type="submit">', 'type="submit" disabled>'),
                         "checkout_submit_unverified")

    def test_31_duplicate_invoice_submit_rejected(self):
        self.assertEqual(self.edited(BUTTON, BUTTON+BUTTON),
                         "checkout_submit_unverified")

    def test_32_wrong_post_target_fails_closed(self):
        self.assertEqual(self.edited("/start/72/", "/start/225/"),
                         "checkout_active_or_ambiguous_markup")

    def test_33_external_post_target_fails_closed(self):
        self.assertEqual(self.edited('action="/commerce/', 'action="https://outside.example/commerce/'),
                         "checkout_active_or_ambiguous_markup")

    def test_34_post_target_with_query_is_not_exact(self):
        self.assertEqual(self.edited('/start/72/"', '/start/72/?tracking=1"'),
                         "checkout_active_or_ambiguous_markup")

    def test_35_duplicate_post_forms_cannot_be_approved(self):
        self.assertEqual(self.category(page()+page()),
                         "checkout_post_form_unverified")

    def test_36_unclosed_form_not_approved(self):
        self.assertEqual(self.edited("</form>", ""),
                         "checkout_active_or_ambiguous_markup")

    def test_37_nested_form_not_approved(self):
        self.assertEqual(self.edited(EMAIL, '<form method="post" action="/commerce/trx-easy/start/72/">'+EMAIL+"</form>"),
                         "checkout_active_or_ambiguous_markup")

    def test_38_novalidate_form_rejected(self):
        self.assertEqual(self.edited('method="post"', 'method="post" novalidate'),
                         "checkout_active_or_ambiguous_markup")

    def test_39_formtarget_override_rejected(self):
        self.assertEqual(self.edited(BUTTON, '<button type="submit" formtarget="_blank">Buy</button>'),
                         "checkout_active_or_ambiguous_markup")

    def test_40_formaction_override_rejected(self):
        self.assertEqual(self.edited(BUTTON, '<button type="submit" formaction="/attacker/">Buy</button>'),
                         "checkout_active_or_ambiguous_markup")

    def test_41_html_base_tag_cannot_redirect_relative_fields(self):
        self.assertEqual(self.edited('<head>', '<head><base href="https://outside.example/">'),
                         "checkout_active_or_ambiguous_markup")

    def test_42_inline_script_conflicts_with_script_src_none(self):
        self.assertEqual(self.edited("</main>", "<script>run()</script></main>"),
                         "checkout_active_or_ambiguous_markup")

    def test_43_external_script_conflicts_with_script_src_none(self):
        self.assertEqual(self.edited("</main>", '<script src="/pay.js"></script></main>'),
                         "checkout_active_or_ambiguous_markup")

    def test_44_inline_onclick_handler_fails_closed(self):
        self.assertEqual(self.edited(BUTTON, '<button type="submit" onclick="pay()">Buy</button>'),
                         "checkout_active_or_ambiguous_markup")

    def test_45_javascript_href_fails_closed(self):
        self.assertEqual(self.edited("</main>", '<a href="javascript:run()">Help</a></main>'),
                         "checkout_active_or_ambiguous_markup")

    def test_46_meta_refresh_fails_closed(self):
        self.assertEqual(self.edited('<head>', '<head><meta http-equiv="refresh" content="0;url=/other/">'),
                         "checkout_active_or_ambiguous_markup")

    def test_47_embedded_iframe_fails_closed(self):
        self.assertEqual(self.edited("</main>", '<iframe src="/other/"></iframe></main>'),
                         "checkout_active_or_ambiguous_markup")

    def test_48_image_submit_rejected(self):
        self.assertEqual(self.edited(BUTTON, '<input type="image" src="/buy.png">'),
                         "checkout_active_or_ambiguous_markup")

    def test_49_duplicate_email_name_attribute_rejected(self):
        self.assertEqual(self.edited('name="email"', 'name="buyer_email" name="email"'),
                         "checkout_active_or_ambiguous_markup")

    def test_50_form_multipart_encoding_rejected(self):
        self.assertEqual(self.edited('method="post"', 'method="post" enctype="multipart/form-data"'),
                         "checkout_active_or_ambiguous_markup")

    def test_51_form_invalid_accept_charset_rejected(self):
        self.assertEqual(self.edited('method="post"', 'method="post" accept-charset="utf-7"'),
                         "checkout_active_or_ambiguous_markup")

    def test_52_duplicate_form_action_rejected(self):
        self.assertEqual(self.edited('action="/commerce/trx-easy/start/72/"',
                                     'action="/commerce/trx-easy/start/72/" action="/elsewhere/"'),
                         "checkout_active_or_ambiguous_markup")

    def test_53_email_input_detached_from_form_rejected(self):
        self.assertEqual(self.category(page().replace(EMAIL, "") + EMAIL),
            "checkout_active_or_ambiguous_markup")

    def test_54_comment_mention_of_script_does_not_change_document(self):
        self.assertEqual(self.edited("<main>", "<main><!-- <script>fake()</script> -->"),
                         "rendered_form_structurally_valid_not_paid")

    def test_55_inline_css_can_be_used_without_script_execution(self):
        self.assertEqual(self.edited("<head>", '<head><style>body{margin:0}</style>'),
                         "rendered_form_structurally_valid_not_paid")

    def test_56_required_email_alias_accepted_without_receipt_claim(self):
        self.assertEqual(self.edited('name="email"', 'name="buyer_email"'),
                         "rendered_form_structurally_valid_not_paid")

    def test_57_invalid_request_fails_with_fixed_non_sensitive_exception(self):
        secret = "secret-buyer-checkout-cookie"
        response = Response(page().replace(EMAIL, '<input value="'+secret+'">'))
        with self.assertRaises(module.CheckoutMarkupError) as caught:
            module.require_checkout_markup(response, 72)
        self.assertNotIn(secret, str(caught.exception))
        self.assertEqual(str(caught.exception), "Buyer checkout form not ready")

    def test_58_success_guard_does_not_change_response_or_send_payment(self):
        response = Response()
        original = response.content
        self.assertIsNone(module.require_checkout_markup(response, 72))
        self.assertEqual(response.content, original)

    def test_59_rendered_checkout_gate_is_called_before_funnel_or_csp(self):
        source = (ROOT / "services/mpw_trx_guest_commerce.py").read_text("utf-8")
        begin = source.index("def _checkout_page(")
        end = source.index("\ndef patch_public(", begin)
        section = source[begin:end]
        self.assertLess(section.index("require_checkout_markup(response, product_id)"),
                        section.index('_record_funnel_event_best_effort(request, "begin_checkout"'))
        self.assertLess(section.index("require_checkout_markup(response, product_id)"),
                        section.index('response["Content-Security-Policy"]'))

    def test_60_contract_module_has_no_network_or_checkout_runtime_imports(self):
        source = SOURCE.read_text("utf-8")
        self.assertNotIn("requests.", source)
        self.assertNotIn("urllib.request", source)
        self.assertNotIn("django.", source)
        self.assertNotIn("EmailMessage", source)


if __name__ == "__main__":
    unittest.main()
