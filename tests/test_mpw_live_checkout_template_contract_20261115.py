"""Render the actual installed Django checkout template, not a mock form."""
from pathlib import Path
from types import SimpleNamespace

from django.conf import settings
from django.http import HttpResponse
from django.middleware.csrf import get_token
from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase

from services.mpw_checkout_render_contract import (
    checkout_markup_category, require_checkout_markup,
)


class InstalledBuyerCheckoutTemplateTests(SimpleTestCase):
    def setUp(self):
        self.request = RequestFactory().get(
            "/store/product/72/checkout/", HTTP_HOST="mojplaywin.com",
            secure=True,
        )
        get_token(self.request)

    def actual_html(self, product_id=72):
        return render_to_string(
            "mpw_commerce/product_checkout.html",
            {"product": SimpleNamespace(pk=product_id,
                                        title="Science of Chess Improvement"),
             "price_usd": "19.90", "mpw_trx_easy_enabled": True},
            request=self.request,
        )

    def test_real_django_checkout_is_one_actionable_email_bound_post(self):
        for product_id in (72,225,879):
            with self.subTest(product_id=product_id):
                body = self.actual_html(product_id)
                result = HttpResponse(body,content_type="text/html; charset=utf-8")
                self.assertEqual(
                    checkout_markup_category(result,product_id),
                    "rendered_form_structurally_valid_not_paid",
                )
                require_checkout_markup(result,product_id)

    def test_template_does_not_ask_wallet_to_sign_or_charge_first(self):
        html = self.actual_html()
        self.assertIn("No money is charged by submitting this form.",html)
        self.assertIn('name="email"',html)
        self.assertIn('type="email"',html)
        self.assertIn('autocomplete="email"',html)
        self.assertNotIn("<script",html.casefold())
        self.assertNotIn("guaranteed profits",html.casefold())
        self.assertNotIn('value="customer@',html.casefold())

    def test_template_is_deployed_in_this_django_project(self):
        path = Path(settings.BASE_DIR)/"core/templates/mpw_commerce/product_checkout.html"
        self.assertTrue(path.is_file())
        self.assertIn("{% csrf_token %}",path.read_text("utf-8"))
