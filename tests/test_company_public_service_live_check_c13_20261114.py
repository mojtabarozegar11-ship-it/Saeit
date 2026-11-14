"""Read-only public commercial visibility contract, without live network tests."""
from io import BytesIO
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from deploy.company_public_service_live_check import CODES, check


class FakeResponse:
    status = 200
    headers = {"Content-Type": "text/html; charset=UTF-8"}

    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self, *_):
        return self.body


class PublicServiceVisibilityTests(unittest.TestCase):
    def test_only_six_authoritative_scopes_are_checked(self):
        self.assertEqual(CODES, ("AGR-01", "RS-01", "RS-02", "RS-03", "WEB-01", "SEO-01"))

    def test_exact_public_rendered_marker_is_required(self):
        class Opener:
            def open(self, request, timeout):
                self.request = request
                return FakeResponse(b'<section class="scope-primary-cta">hello</section>')
        opener = Opener()
        with patch("deploy.company_public_service_live_check.build_opener", return_value=opener):
            out = check("/services/scope/AGR-01/", "scope-primary-cta")
        self.assertEqual(out["status"], "200")
        self.assertTrue(out["marker"])
        self.assertEqual(opener.request.get_method(), "GET")

    def test_generic_200_html_without_actual_service_marker_is_not_ready(self):
        class Opener:
            def open(self, *args, **kwargs):
                return FakeResponse(b"<html>generic error</html>")
        with patch("deploy.company_public_service_live_check.build_opener", return_value=Opener()):
            out = check("/services/scope/AGR-01/", "scope-primary-cta")
        self.assertFalse(out["marker"])
        self.assertEqual(out["reason"], "MARKER_MISSING")

    def test_refuse_path_traversal_query_or_protocol_redirects(self):
        for path in ("//not-company", "/../company", "/anything?secret=1", "/foo#anchor", "https://elsewhere"):
            with self.assertRaises(ValueError):
                check(path, "scope-primary-cta")

    def test_404_is_not_incorrectly_marked_as_a_sale_page(self):
        class Opener:
            def open(self, *args, **kwargs):
                raise HTTPError("https://zomorodmelal.ir/", 404, "Not Found", {}, None)
        with patch("deploy.company_public_service_live_check.build_opener", return_value=Opener()):
            out = check("/services/scope/AGR-01/", "scope-primary-cta")
        self.assertEqual(out["status"], "404")
        self.assertFalse(out["marker"])


if __name__ == "__main__":
    unittest.main()
