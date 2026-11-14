"""No-Django regression for one workable TRX invoice submit per checkout.

Uses the existing production release parser, with no network, DB or deploy.
Passing this suite is not proof of a paid order or blockchain finality.
"""
from __future__ import annotations
import importlib.util
import unittest
from pathlib import Path

RELEASE = Path(__file__).resolve().parents[1] / "scripts/mpw_guest_checkout_live_release.py"
SPEC = importlib.util.spec_from_file_location("mpw_guest_release_submit_contract", RELEASE)
assert SPEC is not None and SPEC.loader is not None
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)
check = mod.has_buyer_email_form
ROUTE = "/commerce/trx-easy/start/72/"
EMAIL = '<input name="email" type="email" required>'
CSRF = '<input type="hidden" name="csrfmiddlewaretoken" value="' + "A"*64 + '">'
BUTTON = '<button type="submit">Create invoice and pay with TRX</button>'

def form(*parts, attrs=""):
    return '<form method="post" action="' + ROUTE + '" ' + attrs + '>' + ''.join(parts) + '</form>'

class RevenueSubmitGateTests(unittest.TestCase):
    def verify(self, html, expected):
        self.assertEqual(check(html, expected_action=ROUTE,
                               require_csrf=True, require_submit=True), expected)

    def test_01_implicit_button_submit(self):
        self.verify(form(EMAIL,CSRF,'<button>Buy</button>'), True)

    def test_02_explicit_button_submit(self):
        self.verify(form(EMAIL,CSRF,BUTTON), True)

    def test_03_input_submit(self):
        self.verify(form(EMAIL,CSRF,'<input type="submit" value="Buy">'), True)

    def test_04_missing_submit(self):
        self.verify(form(EMAIL,CSRF), False)

    def test_05_button_type_button(self):
        self.verify(form(EMAIL,CSRF,'<button type="button">Buy</button>'), False)

    def test_06_disabled_submit(self):
        self.verify(form(EMAIL,CSRF,'<button disabled>Buy</button>'), False)

    def test_07_hidden_submit(self):
        self.verify(form(EMAIL,CSRF,'<button hidden>Buy</button>'), False)

    def test_08_submit_external_form_owner(self):
        self.verify(form(EMAIL,CSRF,'<button form="other">Buy</button>'), False)

    def test_09_submit_formaction_override(self):
        self.verify(form(EMAIL,CSRF,'<button formaction="/pay-elsewhere/">Buy</button>'), False)

    def test_10_submit_formmethod_override(self):
        self.verify(form(EMAIL,CSRF,'<button formmethod="get">Buy</button>'), False)

    def test_11_submit_formnovalidate(self):
        self.verify(form(EMAIL,CSRF,'<button formnovalidate>Buy</button>'), False)

    def test_12_multiple_submit(self):
        self.verify(form(EMAIL,CSRF,BUTTON,BUTTON), False)

    def test_13_submit_in_disabled_fieldset(self):
        self.verify(form(EMAIL,CSRF,'<fieldset disabled>'+BUTTON+'</fieldset>'), False)

    def test_14_submit_in_hidden_parent(self):
        self.verify(form(EMAIL,CSRF,'<div hidden>'+BUTTON+'</div>'), False)

    def test_15_form_enctype_text_plain(self):
        self.verify(form(EMAIL,CSRF,BUTTON,attrs='enctype="text/plain"'), False)

    def test_16_form_target_blank(self):
        self.verify(form(EMAIL,CSRF,BUTTON,attrs='target="_blank"'), False)

    def test_17_form_onsubmit_script(self):
        self.verify(form(EMAIL,CSRF,BUTTON,attrs='onsubmit="return false"'), False)

    def test_18_form_novalidate(self):
        self.verify(form(EMAIL,CSRF,BUTTON,attrs='novalidate'), False)

    def test_19_submit_onclick(self):
        self.verify(form(EMAIL,CSRF,'<button onclick="x()">Buy</button>'), False)

    def test_20_normal_semantic_section(self):
        self.verify('<main><section>'+form(EMAIL,CSRF,BUTTON)+'</section></main>', True)

    def test_21_email_missing(self):
        self.verify(form(CSRF,BUTTON), False)

    def test_22_csrf_missing(self):
        self.verify(form(EMAIL,BUTTON), False)

    def test_23_wrong_product_action(self):
        self.verify('<form method="post" action="/commerce/trx-easy/start/225/">'+EMAIL+CSRF+BUTTON+'</form>', False)

    def test_24_multipart_enctype_rejected(self):
        self.verify(form(EMAIL,CSRF,BUTTON,attrs='enctype="multipart/form-data"'), False)

if __name__ == "__main__":
    unittest.main(verbosity=2)
