"""Full nine-route cutover acceptance with deterministic fake GET only.

Mocks the network boundary. No production requests, POST, emails, TRX or data.
"""
import contextlib
import io
from urllib.parse import urlsplit
import unittest
from unittest.mock import patch

from scripts.mpw_dynamic_store_cutover_20261108 import (
    BUYER_ROUTE_PROBES, verify_public_buyer_routes
)

CSP = ("default-src 'self'; script-src 'none'; form-action 'self'; "
       "frame-ancestors 'none'; base-uri 'self'")
SAFE = {"Content-Type":"text/html; charset=utf-8",
        "Content-Security-Policy":CSP,
        "Cache-Control":"private, no-store, max-age=0"}
INVOICE = b"Create my TRX payment invoice"
EMAIL = b'<input type="email" name="email" required maxlength="254" autocomplete="email">'
TOKEN = b'<input type="hidden" name="csrfmiddlewaretoken" value="' + b'A'*64 + b'">'
BUTTON = b'<button type="submit">Create my TRX payment invoice</button>'
TARGET = "/store/product/72/checkout/"


def content(route, title, action):
    if INVOICE not in action:
        return title + b" " + action
    pid = int(route.split("/")[3])
    return (b'<!doctype html><html><head><title>MojPlayWin checkout</title></head>'
            b'<body><main><h1>' + title + b'</h1><p>' + action + b'</p>'
            + f'<form method="post" action="/commerce/trx-easy/start/{pid}/">'.encode()
            + TOKEN + EMAIL + BUTTON + b'</form></main></body></html>')


class Reply:
    status = 200

    def __init__(self, request, transform):
        self.url = request.full_url
        route = urlsplit(self.url).path
        title, action = next((a,b) for p,a,b in BUYER_ROUTE_PROBES if p == route)
        body = content(route, title, action)
        headers = dict(SAFE)
        if transform:
            body, headers = transform(route, body, headers)
        self.body = body
        self.headers = headers

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def geturl(self):
        return self.url

    def read(self, limit):
        assert limit == 250_001
        return self.body


class RouteEmailGates(unittest.TestCase):
    def _run(self, transform=None):
        paths=[]
        def fetch(req, timeout):
            self.assertEqual(req.get_method(), "GET")
            self.assertTrue(0 < timeout <= 7)
            route = urlsplit(req.full_url).path
            self.assertEqual(urlsplit(req.full_url).hostname, "mojplaywin.com")
            paths.append(route)
            return Reply(req, transform)
        sink = io.StringIO()
        with patch("scripts.mpw_dynamic_store_cutover_20261108.urllib.request.urlopen",
                   side_effect=fetch):
            with contextlib.redirect_stdout(sink):
                accepted=verify_public_buyer_routes("42425162199")
        return accepted, sink.getvalue(), paths

    def _mutate(self, edit, target=TARGET):
        return self._run(lambda p,b,h: edit(b,h) if p==target else (b,h))

    def _body(self, change, expected="checkout_form_invalid"):
        passed, log, paths=self._mutate(lambda b,h:(change(b),h))
        self.assertFalse(passed)
        self.assertIn('"category": "'+expected+'"',log)
        # BUYER_ROUTE_PROBES lists three details first, then three
        # canonical checkouts, then three aliases. First checkout is fourth.
        self.assertEqual(paths[0], "/store/product/72/")
        self.assertEqual(paths[3], TARGET)
        self.assertEqual(len(paths), 4)

    def _header(self, update, expected):
        passed,log,paths=self._mutate(lambda b,h:(b,update(h)))
        self.assertFalse(passed)
        self.assertIn('"category": "'+expected+'"',log)
        self.assertEqual(len(paths),4)

    def test_01_all_nine_real_routes_verified_get_only(self):
        passed,log,paths=self._run()
        self.assertTrue(passed,log)
        self.assertEqual(paths,[p for p,_,_ in BUYER_ROUTE_PROBES])
        self.assertIn('"checked": 9',log)

    def test_02_email_required_on_real_cutover_route(self):
        self._body(lambda b:b.replace(EMAIL,b""))

    def test_03_optional_email_not_accepted(self):
        self._body(lambda b:b.replace(b" required maxlength",b" maxlength"))

    def test_04_text_input_not_email(self):
        self._body(lambda b:b.replace(b'type="email"',b'type="text"'))

    def test_05_multiple_email_fields_not_accepted(self):
        self._body(lambda b:b.replace(EMAIL,EMAIL+EMAIL))

    def test_06_disabled_email_not_accepted(self):
        self._body(lambda b:b.replace(EMAIL,EMAIL[:-1]+b" disabled>"))

    def test_07_readonly_email_not_accepted(self):
        self._body(lambda b:b.replace(EMAIL,EMAIL[:-1]+b" readonly>"))

    def test_08_email_in_inert_fieldset_not_accepted(self):
        self._body(lambda b:b.replace(EMAIL,b"<fieldset disabled>"+EMAIL+b"</fieldset>"))

    def test_09_html_hidden_email_not_accepted(self):
        self._body(lambda b:b.replace(EMAIL,EMAIL[:-1]+b" hidden>"))

    def test_10_email_css_hidden_not_accepted(self):
        self._body(lambda b:b.replace(EMAIL,EMAIL[:-1]+b' style="display:none">'))

    def test_11_email_inputmode_none_not_accepted(self):
        self._body(lambda b:b.replace(EMAIL,EMAIL[:-1]+b' inputmode="none">'))

    def test_12_csrf_missing_not_accepted(self):
        self._body(lambda b:b.replace(TOKEN,b""))

    def test_13_csrf_short_not_accepted(self):
        self._body(lambda b:b.replace(b'A'*64,b"123"))

    def test_14_csrf_inside_disabled_fieldset_not_accepted(self):
        self._body(lambda b:b.replace(TOKEN,b"<fieldset disabled>"+TOKEN+b"</fieldset>"))

    def test_15_duplicate_csrf_not_accepted(self):
        self._body(lambda b:b.replace(TOKEN,TOKEN+TOKEN))

    def test_16_wrong_invoice_post_action_not_accepted(self):
        self._body(lambda b:b.replace(b"/start/72/",b"/start/225/"))

    def test_17_get_invoice_form_not_accepted(self):
        self._body(lambda b:b.replace(b'method="post"',b'method="get"'))

    def test_18_no_invoice_submit_not_accepted(self):
        self._body(lambda b:b.replace(BUTTON,b""))

    def test_19_hidden_submit_not_accepted(self):
        self._body(lambda b:b.replace(BUTTON,BUTTON.replace(b'<button',b'<button hidden')))

    def test_20_duplicate_post_form_not_accepted(self):
        self._body(lambda b:b.replace(b"</main>",b"<form method='post'></form></main>"),
                   expected="checkout_form_invalid")

    def test_21_checkout_inside_hidden_div_not_accepted(self):
        self._body(lambda b:b.replace(b"<main>",b"<main><div hidden>").replace(b"</main>",b"</div></main>"))

    def test_22_markup_active_script_not_accepted(self):
        self._body(lambda b:b.replace(b"</main>",b"<script>alert(1)</script></main>"))

    def test_23_missing_csp_blocks_public_cutover(self):
        self._header(lambda h:{k:v for k,v in h.items() if k!="Content-Security-Policy"}, "checkout_csp_missing")

    def test_24_script_self_not_allowed_at_invoice(self):
        self._header(lambda h:{**h,"Content-Security-Policy":CSP.replace("script-src 'none'","script-src 'self'")},
                     "checkout_script_policy_unverified")

    def test_25_duplicate_script_directive_not_allowed(self):
        self._header(lambda h:{**h,"Content-Security-Policy":CSP+"; script-src 'none'"},
                     "checkout_csp_ambiguous")

    def test_26_missing_form_action_rejected(self):
        self._header(lambda h:{**h,"Content-Security-Policy":CSP.replace("form-action 'self'; ","")},
                     "checkout_form_action_policy_unverified")

    def test_27_missing_frame_ancestors_rejected(self):
        self._header(lambda h:{**h,"Content-Security-Policy":CSP.replace("; frame-ancestors 'none'","")},
                     "checkout_frame_policy_unverified")

    def test_28_missing_base_uri_rejected(self):
        self._header(lambda h:{**h,"Content-Security-Policy":CSP.replace("; base-uri 'self'","")},
                     "checkout_base_policy_unverified")

    def test_29_no_store_required_before_cutover(self):
        self._header(lambda h:{**h,"Cache-Control":"private"},
                     "checkout_no_store_unverified")

    def test_30_content_type_html_required(self):
        self._header(lambda h:{**h,"Content-Type":"application/json"},
                     "checkout_content_type_unverified")

    def test_31_second_alias_checkout_missing_email_blocks_all(self):
        passed,log,paths=self._mutate(lambda b,h:(b.replace(EMAIL,b""),h),
                    "/commerce/book/72/")
        self.assertFalse(passed)
        self.assertIn('"category": "checkout_form_invalid"',log)
        self.assertEqual(len(paths),7)

    def test_32_sku_879_checkout_wrong_email_blocks(self):
        passed,log,paths=self._mutate(lambda b,h:(b.replace(EMAIL,b""),h),
                    "/store/product/879/checkout/")
        self.assertFalse(passed)
        self.assertIn('"category": "checkout_form_invalid"',log)

    def test_33_server_fallback_missing_csp_is_not_paid_proof(self):
        passed,log,paths=self._run()
        self.assertTrue(passed)
        self.assertNotIn("payment_verified",log)
        self.assertNotIn("buyer_email",log)
        self.assertNotIn("AAAA",log)

    def test_34_empty_headers_fail_closed(self):
        self._header(lambda h:{}, "checkout_content_type_unverified")

    def test_35_strict_no_redirect_rule_is_unchanged(self):
        passed,log,paths=self._run()
        self.assertTrue(passed)
        self.assertEqual(len(paths),9)
