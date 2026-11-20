import json

from django.http import Http404
from django.test import RequestFactory, SimpleTestCase, override_settings

from .staging_identity_views import (
    staging_identity_activate,
    staging_identity_challenge,
    staging_identity_consume,
    staging_identity_register,
)


@override_settings(
    MPW_MOJPROP_DB_ALIAS_ENABLED=True,
    MPW_MOJPROP_DEPLOYMENT_ENV="staging",
    MPW_MOJPROP_STAGING_IDENTITY_ROUTE_ENABLED=True,
    MPW_MOJPROP_STAGING_ROUTE_TOKEN="s" * 40,
    MPW_MOJPROP_STAGING_INTERNAL_IPS=("127.0.0.1",),
)
class StagingIdentityRouteTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.headers = {
            "HTTP_X_MOJPROP_STAGING_TOKEN": "s" * 40,
            "REMOTE_ADDR": "127.0.0.1",
        }

    def request(self, view, payload, **extra):
        headers = dict(self.headers)
        headers.update(extra)
        request = self.factory.post(
            "/internal/mojprop/staging/identity/",
            data=json.dumps(payload),
            content_type="application/json",
            **headers,
        )
        return view(request)

    def test_missing_token_is_hidden(self):
        request = self.factory.post(
            "/internal/mojprop/staging/identity/register/",
            data="{}",
            content_type="application/json",
            REMOTE_ADDR="127.0.0.1",
        )
        with self.assertRaises(Http404):
            staging_identity_register(request)

    def test_non_loopback_source_is_hidden(self):
        request = self.factory.post(
            "/internal/mojprop/staging/identity/register/",
            data="{}",
            content_type="application/json",
            HTTP_X_MOJPROP_STAGING_TOKEN="s" * 40,
            REMOTE_ADDR="203.0.113.10",
        )
        with self.assertRaises(Http404):
            staging_identity_register(request)

    def test_malformed_payload_fails_without_db_write(self):
        response = self.request(staging_identity_register, {"email": "bad"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(json.loads(response.content)["ok"], False)

    def test_challenge_code_is_never_returned(self):
        response = self.request(staging_identity_challenge, {"identity_id": 999999})
        self.assertEqual(response.status_code, 400)
        self.assertNotIn(b'"code"', response.content)

    def test_consume_rejects_missing_challenge_without_commerce(self):
        response = self.request(staging_identity_consume, {})
        self.assertEqual(response.status_code, 400)
        self.assertNotIn(b'"invoice"', response.content)
        self.assertNotIn(b'"payment"', response.content)

    def test_activate_rejects_unbounded_identity_id(self):
        response = self.request(staging_identity_activate, {"identity_id": 0})
        self.assertEqual(response.status_code, 400)
