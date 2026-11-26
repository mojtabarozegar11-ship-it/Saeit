from pathlib import Path

from django.http import HttpResponse
from django.test import SimpleTestCase
from django.test.client import RequestFactory

from services.mojprop_standalone_boundary import (
    MOJPROP_HOSTS,
    guard_legacy_commerce,
    is_mojprop_host,
    standalone_commerce_unavailable,
)


class MojPropStandaloneBoundaryTests(SimpleTestCase):
    def test_only_dedicated_hosts_are_mojprop(self):
        self.assertEqual(MOJPROP_HOSTS, {"mojprop.top", "www.mojprop.top"})
        factory = RequestFactory()
        request = factory.get("/", secure=True, HTTP_HOST="mojprop.top")
        self.assertTrue(is_mojprop_host(request))
        legacy = factory.get("/", secure=True, HTTP_HOST="mojplaywin.com")
        self.assertFalse(is_mojprop_host(legacy))

    def test_shared_checkout_is_non_payment_on_mojprop(self):
        factory = RequestFactory()
        request = factory.get("/commerce/trx-easy/invoice/54/", secure=True, HTTP_HOST="mojprop.top")
        response = standalone_commerce_unavailable(request)
        self.assertEqual(response.status_code, 503)
        self.assertIn(b"No payment", response.content)
        self.assertEqual(response["X-MojProp-Commerce"], "standalone-not-released")

    def test_guard_does_not_change_legacy_host(self):
        factory = RequestFactory()
        view = guard_legacy_commerce(lambda request: HttpResponse("legacy"))
        legacy = factory.get("/", secure=True, HTTP_HOST="mojplaywin.com")
        self.assertEqual(view(legacy).content, b"legacy")
        dedicated = factory.get("/", secure=True, HTTP_HOST="mojprop.top")
        self.assertEqual(view(dedicated).status_code, 503)

    def test_home_templates_contain_no_legacy_brand_or_domain(self):
        root = Path(__file__).resolve().parents[1]
        for relative in ("templates/moj-prop-v4/index.html", "templates/moj-prop/index.html"):
            text = (root / relative).read_text(encoding="utf-8")
            self.assertNotIn("mojplaywin.com", text)
            self.assertNotIn("MojPlayWin", text)
            self.assertNotIn("MOJPLAYWIN", text)
            self.assertIn("mojprop.top", text.lower())
