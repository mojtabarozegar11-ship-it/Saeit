"""Read-only synthetic checkout-email acceptance tests.

These tests never reach the network, SSH, cPanel, mail, or payment systems.
A static HTML field is a *candidate*, not a paid/usable live checkout.
"""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/mpw_onepass_cpanel_source_provenance_readonly_20261113.py"
_spec = importlib.util.spec_from_file_location("mpw_source_inspector_20261114", SCRIPT)
_probe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_probe)


def parse_static(html):
    scanner = _probe.StaticCheckoutControlInspector()
    scanner.feed(html)
    scanner.close()
    return scanner


class StaticCheckoutEmailRegression(unittest.TestCase):
    def test_valid_post_email_source_is_only_static_candidate(self):
        p = parse_static("<form method=\"post\" action=\"/commerce/trx-easy/start/72/\"><input type=\"email\" name=\"buyer_email\" required></form>")
        self.assertEqual(p.email_controls, 1)
        self.assertEqual(p.email_hints, 1)
        self.assertEqual(p.post_forms, 1)
        self.assertEqual(p.forms, 1)
        self.assertFalse(p.rejection_codes)

    def test_valid_product_aliases_not_limited_to_sku_72(self):
        for sku in (72, 225, 879):
            with self.subTest(sku=sku):
                html = '<form method="post" action="/commerce/trx-easy/start/{}/">'.format(sku) + "<input type=\"email\" name=\"buyer_email\" required></form>"
                self.assertEqual(parse_static(html).email_controls, 1)

    def test_uppercase_html_input_and_form_is_supported(self):
        html="<FORM METHOD=\"POST\" ACTION=\"/COMMERCE/TRX-EASY/START/72/\"><INPUT TYPE=\"EMAIL\" NAME=\"BUYER_EMAIL\" REQUIRED></FORM>"
        self.assertEqual(parse_static(html).email_controls, 1)

    def test_multiple_email_fields_are_not_source_ready(self):
        p=parse_static("<form method=\"post\" action=\"/commerce/trx-easy/start/72/\"><input type=\"email\" name=\"buyer_email\" required><input type=\"email\" name=\"buyer_email\" required></form>")
        self.assertEqual(p.email_controls, 2)
        self.assertNotEqual(p.email_controls, 1)

    def test_nested_forms_are_flagged_ambiguous(self):
        p=parse_static("<form method=\"post\" action=\"/commerce/trx-easy/start/72/\"><form method=\"post\" action=\"/commerce/trx-easy/start/72/\"><input type=\"email\" name=\"buyer_email\" required></form></form>")
        self.assertIn("nested_form",p.rejection_codes)

    def test_public_report_never_certifies_payment_on_source_basis(self):
        source=SCRIPT.read_text()
        self.assertIn('"production_invoice_post_verified": False', source)
        self.assertIn('"independent_chain_finality_verified": False', source)
        self.assertIn('"authenticated_delivery_verified": False', source)
        self.assertIn('"production_release_permitted_by_this_report": False', source)
        self.assertIn('"template_usable_email_controls_count_capped"', source)
        self.assertIn('"template_email_rejections"', source)

    def test_gate_01_get_instead_of_post(self):
        p=parse_static("<form method=\"get\" action=\"/commerce/trx-easy/start/72/\"><input type=\"email\" name=\"buyer_email\" required></form>")
        self.assertEqual(p.email_controls, 0)

    def test_gate_02_default_get(self):
        p=parse_static("<form  action=\"/commerce/trx-easy/start/72/\"><input type=\"email\" name=\"buyer_email\" required></form>")
        self.assertEqual(p.email_controls, 0)

    def test_gate_03_missing_action(self):
        p=parse_static("<form method=\"post\"><input type=\"email\" name=\"buyer_email\" required></form>")
        self.assertEqual(p.email_controls, 0)

    def test_gate_04_offsite_action(self):
        p=parse_static("<form method=\"post\" action=\"https://evil.example/start/72/\"><input type=\"email\" name=\"buyer_email\" required></form>")
        self.assertEqual(p.email_controls, 0)

    def test_gate_05_protocol_relative_action(self):
        p=parse_static("<form method=\"post\" action=\"//other.example/commerce/trx-easy/start/72/\"><input type=\"email\" name=\"buyer_email\" required></form>")
        self.assertEqual(p.email_controls, 0)

    def test_gate_06_relative_action(self):
        p=parse_static("<form method=\"post\" action=\"commerce/trx-easy/start/72/\"><input type=\"email\" name=\"buyer_email\" required></form>")
        self.assertEqual(p.email_controls, 0)

    def test_gate_07_zero_product_id(self):
        p=parse_static("<form method=\"post\" action=\"/commerce/trx-easy/start/0/\"><input type=\"email\" name=\"buyer_email\" required></form>")
        self.assertEqual(p.email_controls, 0)

    def test_gate_08_negative_product_id(self):
        p=parse_static("<form method=\"post\" action=\"/commerce/trx-easy/start/-72/\"><input type=\"email\" name=\"buyer_email\" required></form>")
        self.assertEqual(p.email_controls, 0)

    def test_gate_09_querystring_on_action(self):
        p=parse_static("<form method=\"post\" action=\"/commerce/trx-easy/start/72/?utm=x\"><input type=\"email\" name=\"buyer_email\" required></form>")
        self.assertEqual(p.email_controls, 0)

    def test_gate_10_form_novalidate(self):
        p=parse_static("<form method=\"post\" action=\"/commerce/trx-easy/start/72/\" novalidate><input type=\"email\" name=\"buyer_email\" required></form>")
        self.assertEqual(p.email_controls, 0)

    def test_gate_11_form_target(self):
        p=parse_static("<form method=\"post\" action=\"/commerce/trx-easy/start/72/\" target=\"_blank\"><input type=\"email\" name=\"buyer_email\" required></form>")
        self.assertEqual(p.email_controls, 0)

    def test_gate_12_multipart_form(self):
        p=parse_static("<form method=\"post\" action=\"/commerce/trx-easy/start/72/\" enctype=\"multipart/form-data\"><input type=\"email\" name=\"buyer_email\" required></form>")
        self.assertEqual(p.email_controls, 0)

    def test_gate_13_unsupported_charset(self):
        p=parse_static("<form method=\"post\" action=\"/commerce/trx-easy/start/72/\" accept-charset=\"UTF-16\"><input type=\"email\" name=\"buyer_email\" required></form>")
        self.assertEqual(p.email_controls, 0)

    def test_gate_14_duplicate_method(self):
        p=parse_static("<form method=\"post\" action=\"/commerce/trx-easy/start/72/\" method=\"post\"><input type=\"email\" name=\"buyer_email\" required></form>")
        self.assertEqual(p.email_controls, 0)

    def test_gate_15_duplicate_action(self):
        p=parse_static("<form method=\"post\" action=\"/commerce/trx-easy/start/72/\" action=\"/commerce/trx-easy/start/72/\"><input type=\"email\" name=\"buyer_email\" required></form>")
        self.assertEqual(p.email_controls, 0)

    def test_gate_16_no_email_name(self):
        p=parse_static("<form method=\"post\" action=\"/commerce/trx-easy/start/72/\"><input type=\"email\" required></form>")
        self.assertEqual(p.email_controls, 0)

    def test_gate_17_wrong_email_name(self):
        p=parse_static("<form method=\"post\" action=\"/commerce/trx-easy/start/72/\"><input type=\"email\" name=\"recipient\" required></form>")
        self.assertEqual(p.email_controls, 0)

    def test_gate_18_text_input_instead_of_email(self):
        p=parse_static("<form method=\"post\" action=\"/commerce/trx-easy/start/72/\"><input type=\"text\" name=\"buyer_email\" required></form>")
        self.assertEqual(p.email_controls, 0)

    def test_gate_19_hidden_input_instead_of_email(self):
        p=parse_static("<form method=\"post\" action=\"/commerce/trx-easy/start/72/\"><input type=\"hidden\" name=\"buyer_email\" required></form>")
        self.assertEqual(p.email_controls, 0)

    def test_gate_20_not_required(self):
        p=parse_static("<form method=\"post\" action=\"/commerce/trx-easy/start/72/\"><input type=\"email\" name=\"buyer_email\"></form>")
        self.assertEqual(p.email_controls, 0)

    def test_gate_21_disabled_control(self):
        p=parse_static("<form method=\"post\" action=\"/commerce/trx-easy/start/72/\"><input type=\"email\" name=\"buyer_email\" required disabled></form>")
        self.assertEqual(p.email_controls, 0)

    def test_gate_22_readonly_control(self):
        p=parse_static("<form method=\"post\" action=\"/commerce/trx-easy/start/72/\"><input type=\"email\" name=\"buyer_email\" required readonly></form>")
        self.assertEqual(p.email_controls, 0)

    def test_gate_23_multiple_emails(self):
        p=parse_static("<form method=\"post\" action=\"/commerce/trx-easy/start/72/\"><input type=\"email\" name=\"buyer_email\" required multiple></form>")
        self.assertEqual(p.email_controls, 0)

    def test_gate_24_unsupported_email_pattern(self):
        p=parse_static("<form method=\"post\" action=\"/commerce/trx-easy/start/72/\"><input type=\"email\" name=\"buyer_email\" required pattern=\"foo\"></form>")
        self.assertEqual(p.email_controls, 0)

    def test_gate_25_inputmode_none(self):
        p=parse_static("<form method=\"post\" action=\"/commerce/trx-easy/start/72/\"><input type=\"email\" name=\"buyer_email\" required inputmode=\"none\"></form>")
        self.assertEqual(p.email_controls, 0)

    def test_gate_26_hidden_input_attr(self):
        p=parse_static("<form method=\"post\" action=\"/commerce/trx-easy/start/72/\"><input type=\"email\" name=\"buyer_email\" required hidden></form>")
        self.assertEqual(p.email_controls, 0)

    def test_gate_27_inert_input_attr(self):
        p=parse_static("<form method=\"post\" action=\"/commerce/trx-easy/start/72/\"><input type=\"email\" name=\"buyer_email\" required inert></form>")
        self.assertEqual(p.email_controls, 0)

    def test_gate_28_aria_hidden_input(self):
        p=parse_static("<form method=\"post\" action=\"/commerce/trx-easy/start/72/\"><input type=\"email\" name=\"buyer_email\" required aria-hidden=\"true\"></form>")
        self.assertEqual(p.email_controls, 0)

    def test_gate_29_aria_disabled_input(self):
        p=parse_static("<form method=\"post\" action=\"/commerce/trx-easy/start/72/\"><input type=\"email\" name=\"buyer_email\" required aria-disabled=\"true\"></form>")
        self.assertEqual(p.email_controls, 0)

    def test_gate_30_style_display_none(self):
        p=parse_static("<form method=\"post\" action=\"/commerce/trx-easy/start/72/\"><input type=\"email\" name=\"buyer_email\" required style=\"display: none\"></form>")
        self.assertEqual(p.email_controls, 0)

    def test_gate_31_style_visibility_hidden(self):
        p=parse_static("<form method=\"post\" action=\"/commerce/trx-easy/start/72/\"><input type=\"email\" name=\"buyer_email\" required style=\"visibility: hidden\"></form>")
        self.assertEqual(p.email_controls, 0)

    def test_gate_32_style_opacity_zero(self):
        p=parse_static("<form method=\"post\" action=\"/commerce/trx-easy/start/72/\"><input type=\"email\" name=\"buyer_email\" required style=\"opacity: 0\"></form>")
        self.assertEqual(p.email_controls, 0)

    def test_gate_33_style_pointer_events_none(self):
        p=parse_static("<form method=\"post\" action=\"/commerce/trx-easy/start/72/\"><input type=\"email\" name=\"buyer_email\" required style=\"pointer-events:none\"></form>")
        self.assertEqual(p.email_controls, 0)

    def test_gate_34_maxlength_too_short(self):
        p=parse_static("<form method=\"post\" action=\"/commerce/trx-easy/start/72/\"><input type=\"email\" name=\"buyer_email\" required maxlength=\"5\"></form>")
        self.assertEqual(p.email_controls, 0)

    def test_gate_35_maxlength_too_large(self):
        p=parse_static("<form method=\"post\" action=\"/commerce/trx-easy/start/72/\"><input type=\"email\" name=\"buyer_email\" required maxlength=\"255\"></form>")
        self.assertEqual(p.email_controls, 0)

    def test_gate_36_minlength_over_maxlength(self):
        p=parse_static("<form method=\"post\" action=\"/commerce/trx-easy/start/72/\"><input type=\"email\" name=\"buyer_email\" required minlength=\"20\" maxlength=\"10\"></form>")
        self.assertEqual(p.email_controls, 0)

    def test_gate_37_duplicate_name_attr(self):
        p=parse_static("<form method=\"post\" action=\"/commerce/trx-easy/start/72/\"><input type=\"email\" name=\"buyer_email\" required name=\"buyer_email\"></form>")
        self.assertEqual(p.email_controls, 0)

    def test_gate_38_duplicate_type_attr(self):
        p=parse_static("<form method=\"post\" action=\"/commerce/trx-easy/start/72/\"><input type=\"email\" name=\"buyer_email\" required type=\"email\"></form>")
        self.assertEqual(p.email_controls, 0)

    def test_gate_39_formaction_override(self):
        p=parse_static("<form method=\"post\" action=\"/commerce/trx-easy/start/72/\"><input type=\"email\" name=\"buyer_email\" required formaction=\"https://evil.example\"></form>")
        self.assertEqual(p.email_controls, 0)

    def test_gate_40_formmethod_override(self):
        p=parse_static("<form method=\"post\" action=\"/commerce/trx-easy/start/72/\"><input type=\"email\" name=\"buyer_email\" required formmethod=\"get\"></form>")
        self.assertEqual(p.email_controls, 0)

    def test_gate_41_formtarget_override(self):
        p=parse_static("<form method=\"post\" action=\"/commerce/trx-easy/start/72/\"><input type=\"email\" name=\"buyer_email\" required formtarget=\"_blank\"></form>")
        self.assertEqual(p.email_controls, 0)

    def test_gate_42_hidden_parent(self):
        p=parse_static("<form method=\"post\" action=\"/commerce/trx-easy/start/72/\"><section hidden><input type=\"email\" name=\"buyer_email\" required></section></form>")
        self.assertEqual(p.email_controls, 0)

    def test_gate_43_inert_parent(self):
        p=parse_static("<form method=\"post\" action=\"/commerce/trx-easy/start/72/\"><div inert><input type=\"email\" name=\"buyer_email\" required></div></form>")
        self.assertEqual(p.email_controls, 0)

    def test_gate_44_aria_hidden_parent(self):
        p=parse_static("<form method=\"post\" action=\"/commerce/trx-easy/start/72/\"><div aria-hidden=\"true\"><input type=\"email\" name=\"buyer_email\" required></div></form>")
        self.assertEqual(p.email_controls, 0)

    def test_gate_45_fieldset_disabled_parent(self):
        p=parse_static("<form method=\"post\" action=\"/commerce/trx-easy/start/72/\"><fieldset disabled><input type=\"email\" name=\"buyer_email\" required></fieldset></form>")
        self.assertEqual(p.email_controls, 0)

    def test_gate_46_template_element(self):
        p=parse_static("<form method=\"post\" action=\"/commerce/trx-easy/start/72/\"><template><input type=\"email\" name=\"buyer_email\" required></template></form>")
        self.assertEqual(p.email_controls, 0)

    def test_gate_47_closed_details(self):
        p=parse_static("<form method=\"post\" action=\"/commerce/trx-easy/start/72/\"><details><input type=\"email\" name=\"buyer_email\" required></details></form>")
        self.assertEqual(p.email_controls, 0)

    def test_gate_48_closed_dialog(self):
        p=parse_static("<form method=\"post\" action=\"/commerce/trx-easy/start/72/\"><dialog><input type=\"email\" name=\"buyer_email\" required></dialog></form>")
        self.assertEqual(p.email_controls, 0)

    def test_gate_49_email_textarea(self):
        p=parse_static("<form method=\"post\" action=\"/commerce/trx-easy/start/72/\"><textarea name=\"buyer_email\" required></textarea></form>")
        self.assertEqual(p.email_controls, 0)

    def test_gate_50_email_select(self):
        p=parse_static("<form method=\"post\" action=\"/commerce/trx-easy/start/72/\"><select name=\"buyer_email\" required></select></form>")
        self.assertEqual(p.email_controls, 0)

    def test_gate_51_detached_input(self):
        p=parse_static("<input type=\"email\" name=\"buyer_email\" required><form method=\"post\" action=\"/commerce/trx-easy/start/72/\"></form>")
        self.assertEqual(p.email_controls, 0)

    def test_gate_52_unclosed_post_form(self):
        p=parse_static("<form method=\"post\" action=\"/commerce/trx-easy/start/72/\"><input type=\"email\" name=\"buyer_email\" required>")
        self.assertEqual(p.email_controls, 0)

    def test_gate_53_only_autocomplete_email(self):
        p=parse_static("<form method=\"post\" action=\"/commerce/trx-easy/start/72/\"><input name=\"phone\" type=\"text\" autocomplete=\"email\" required></form>")
        self.assertEqual(p.email_controls, 0)

    def test_gate_54_only_id_email(self):
        p=parse_static("<form method=\"post\" action=\"/commerce/trx-easy/start/72/\"><input name=\"phone\" type=\"text\" id=\"buyer-email\" required></form>")
        self.assertEqual(p.email_controls, 0)

if __name__ == "__main__":
    unittest.main()
