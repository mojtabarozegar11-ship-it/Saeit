"""Deterministic GET-only funnel checks; no outbound traffic in tests."""
import importlib.util
from pathlib import Path
import io
import unittest
import urllib.error
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "lead_audit", ROOT / "scripts/zomorod_live_lead_route_readonly_20261114.py")
M = importlib.util.module_from_spec(SPEC)
import sys
sys.modules[SPEC.name] = M
SPEC.loader.exec_module(M)

STORE_HTML = '<html><a href="/ask-master/index.php?service=1">استعلام</a><a href="tel:+989022048691">تماس</a></html>'
FORM_HTML = '<form method="post" action="/ask-master/index.php?service=1"><input name="name" type="text"><button type="submit">ثبت درخواست</button></form>'

class FakeResponse:
    def __init__(self, status=200, text=STORE_HTML, mime="text/html; charset=utf-8"):
        self.status = status
        self.headers = {"Content-Type": mime}
        self.buf = io.BytesIO(text.encode("utf-8"))
    def __enter__(self): return self
    def __exit__(self, *args): self.buf.close()
    def read(self, n): return self.buf.read(n)

class ReadOnlyAuditTests(unittest.TestCase):
    def fetcher(self, store=STORE_HTML, form=FORM_HTML, contact_status=302, contact_location=M.FORM):
        def fetch(path):
            if path == M.STORE: return M.Observation(200, html=store)
            if path == M.FORM: return M.Observation(200, html=form)
            return M.Observation(contact_status, redirect=contact_location)
        return fetch

    def test_valid_lead_route_qualified_not_a_sale(self):
        r = M.diagnose(self.fetcher())
        self.assertTrue(r["lead_get_route_qualified"])
        self.assertFalse(r["payment_received_verified"])
        self.assertFalse(r["customer_leads_received_verified"])

    def test_broken_form_blocks(self):
        r = M.diagnose(self.fetcher(form="<p>Service unavailable</p>"))
        self.assertFalse(r["lead_get_route_qualified"])

    def test_store_without_inquiry_link_blocks(self):
        r = M.diagnose(self.fetcher(store='<a href="tel:+989022048691">تماس</a>'))
        self.assertFalse(r["store_inquiry_link_observed"])

    def test_missing_phone_blocks(self):
        r = M.diagnose(self.fetcher(store='<a href="/ask-master/index.php?service=1">درخواست</a>'))
        self.assertFalse(r["lead_get_route_qualified"])

    def test_external_form_action_is_rejected(self):
        self.assertFalse(M.safe_form_action("https://attacker.example/collect"))
        self.assertFalse(M.diagnose(self.fetcher(form=FORM_HTML.replace('/ask-master/index.php?service=1','https://attacker.example/collect')))["lead_get_route_qualified"])

    def test_javascript_form_action_is_rejected(self):
        self.assertFalse(M.safe_form_action("javascript:alert(1)"))

    def test_local_form_action_allowed(self):
        self.assertTrue(M.safe_form_action("/ask-master/index.php?service=1"))

    def test_contact_redirect_to_form_allowed(self):
        self.assertTrue(M.expected_location("/ask-master/index.php?service=1"))

    def test_contact_redirect_to_external_origin_denied(self):
        self.assertFalse(M.expected_location("https://evil.example/ask-master/index.php?service=1"))

    def test_bad_contact_redirect_denied(self):
        r = M.diagnose(self.fetcher(contact_location="/wrong-page"))
        self.assertFalse(r["contact_route_usable_or_redirects_to_form"])

    def test_get_only_and_no_authentication_headers(self):
        class FakeOpener:
            def open(self, request, timeout):
                self.req = request
                self.timeout = timeout
                return FakeResponse()
        op = FakeOpener()
        M.fetch_public(M.STORE, opener=op)
        self.assertEqual(op.req.get_method(), "GET")
        self.assertEqual(op.timeout, M.TIMEOUT_SECONDS)
        self.assertNotIn("Cookie", op.req.headers)
        self.assertNotIn("Authorization", op.req.headers)

    def test_only_three_fixed_paths_permitted(self):
        with self.assertRaises(ValueError): M.fetch_public("/admin/")
        self.assertEqual(len(M.PATHS), 3)

    def test_redirect_is_never_followed_automatically(self):
        self.assertIsNone(M.NeverRedirect().redirect_request(None,None,None,None,None,None))

    def test_oversized_html_is_discarded(self):
        class HugeOpener:
            def open(self, req, timeout):
                return FakeResponse(text="x"*(M.MAX_BYTES+1))
        r = M.fetch_public(M.STORE, opener=HugeOpener())
        self.assertEqual(r.issue, "html_too_large")
        self.assertEqual(r.html, "")

    def test_non_html_response_rejected(self):
        class JsonOpener:
            def open(self, req, timeout):
                return FakeResponse(mime="application/json")
        self.assertEqual(M.fetch_public(M.STORE, opener=JsonOpener()).issue, "unexpected_content_type")

    def test_http_404_is_reported_without_claim_of_transport_failure(self):
        class MissingOpener:
            def open(self, req, timeout):
                raise urllib.error.HTTPError(req.full_url,404,"Not found",{},None)
        self.assertEqual(M.fetch_public(M.FORM, opener=MissingOpener()).status,404)

    def test_no_post_payment_or_output_of_customer_data(self):
        r = M.diagnose(self.fetcher())
        for key in ("forms_submitted","remote_writes","lead_submissions_sent"):
            self.assertEqual(r[key],0)
        self.assertFalse(r["credentials_used"])
        self.assertNotIn("html", str(r).lower())

    def test_three_gets_distinguished_from_zero_customer_submissions(self):
        r = M.diagnose(self.fetcher())
        self.assertEqual(r["http_get_requests"], 3)
        self.assertEqual(r["lead_submissions_sent"], 0)
        self.assertNotIn("requests_sent", r)

    def test_form_get_method_is_not_sufficient(self):
        r = M.diagnose(self.fetcher(form=FORM_HTML.replace('method="post"','method="get"')))
        self.assertFalse(r["form_post_fields_and_submit_observed"])

    def test_form_missing_submit_is_not_sufficient(self):
        r = M.diagnose(self.fetcher(form=FORM_HTML.replace('<button type="submit">ثبت درخواست</button>','')))
        self.assertFalse(r["form_post_fields_and_submit_observed"])

    def test_store_source_explicitly_disables_payment(self):
        src = (ROOT / "content/zomorod-v11/store_index.php").read_text("utf-8")
        self.assertIn("در این وضعیت خرید آنلاین و برداشت وجه غیرفعال است",src)
        self.assertIn('href="/ask-master/index.php?service=1"',src)
        self.assertIn('href="tel:+989022048691"',src)

if __name__ == "__main__":
    unittest.main()
