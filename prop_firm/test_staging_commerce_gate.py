import json

from django.test import RequestFactory, SimpleTestCase, override_settings

from .staging_commerce_gate import (
    CommerceGateClosed,
    REQUIRED_GATES,
    evaluate_nonpayable_preview,
)
from .staging_commerce_views import staging_commerce_preview


def all_gates():
    return {name: True for name in REQUIRED_GATES}


class NonPayablePreviewTests(SimpleTestCase):
    def test_all_gates_produce_nonpayable_preview_only(self):
        result = evaluate_nonpayable_preview(
            product_code="MOJ-PROP-01", country="ca", gates=all_gates()
        )
        self.assertTrue(result.eligible_for_preview)
        self.assertFalse(result.payable)
        self.assertFalse(result.settlement_allowed)
        self.assertFalse(result.public_route_allowed)

    def test_missing_kyc_and_refund_stay_blocked(self):
        gates = all_gates()
        gates["kyc_verified"] = False
        gates["refund_policy_accepted"] = False
        result = evaluate_nonpayable_preview(
            product_code="MOJ-PROP-01", country="CA", gates=gates
        )
        self.assertFalse(result.eligible_for_preview)
        self.assertEqual(
            result.missing_gates,
            ("kyc_verified", "refund_policy_accepted"),
        )

    def test_untrusted_gate_type_is_rejected(self):
        gates = all_gates()
        gates["kyc_verified"] = 1
        with self.assertRaises(CommerceGateClosed):
            evaluate_nonpayable_preview(
                product_code="MOJ-PROP-01", country="CA", gates=gates
            )

    def test_product_and_country_are_canonical(self):
        with self.assertRaises(CommerceGateClosed):
            evaluate_nonpayable_preview(
                product_code="OTHER", country="CA", gates=all_gates()
            )
        with self.assertRaises(CommerceGateClosed):
            evaluate_nonpayable_preview(
                product_code="MOJ-PROP-01", country="CAN", gates=all_gates()
            )

    @override_settings(
        MPW_MOJPROP_DB_ALIAS_ENABLED=True,
        MPW_MOJPROP_DEPLOYMENT_ENV="staging",
        MPW_MOJPROP_STAGING_IDENTITY_ROUTE_ENABLED=True,
        MPW_MOJPROP_STAGING_ROUTE_TOKEN="s" * 40,
        MPW_MOJPROP_STAGING_INTERNAL_IPS=("127.0.0.1",),
    )
    def test_http_preview_never_becomes_payable(self):
        request = RequestFactory().post(
            "/internal/mojprop/staging/commerce/preview/",
            data=json.dumps(
                {
                    "product_code": "MOJ-PROP-01",
                    "country": "CA",
                    "gates": all_gates(),
                }
            ),
            content_type="application/json",
            HTTP_X_MOJPROP_STAGING_TOKEN="s" * 40,
            REMOTE_ADDR="127.0.0.1",
        )
        response = staging_commerce_preview(request)
        body = json.loads(response.content)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(body["eligible_for_preview"])
        self.assertFalse(body["payable"])
        self.assertFalse(body["settlement_allowed"])
        self.assertFalse(body["public_route_allowed"])
        self.assertFalse(body["invoice_created"])

    @override_settings(
        MPW_MOJPROP_DB_ALIAS_ENABLED=True,
        MPW_MOJPROP_DEPLOYMENT_ENV="staging",
        MPW_MOJPROP_STAGING_IDENTITY_ROUTE_ENABLED=True,
        MPW_MOJPROP_STAGING_ROUTE_TOKEN="s" * 40,
        MPW_MOJPROP_STAGING_INTERNAL_IPS=("127.0.0.1",),
    )
    def test_enabled_urlconf_registers_commerce_preview_from_view_module(self):
        import importlib

        from django.urls import clear_url_caches
        import config.urls as urlconf

        clear_url_caches()
        loaded = importlib.reload(urlconf)
        names = {getattr(pattern, "name", None) for pattern in loaded.urlpatterns if getattr(pattern, "name", None)}
        self.assertIn("mojprop_staging_commerce_preview", names)

    def test_source_has_no_commerce_side_effect_markers(self):
        source = open(__file__.replace("test_staging_commerce_gate.py", "staging_commerce_gate.py"), encoding="utf-8").read()
        for forbidden in ("create_invoice", "broadcast", "payout", "place_order"):
            self.assertNotIn(forbidden, source)
