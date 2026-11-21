"""Regression tests for the MojPlayWin-hosted canonical assistant entry.

All tests are read-only: no model/API calls, payment, task scheduling or bot start.
"""
import re
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, SimpleTestCase
from django.urls import resolve, reverse

from core.mojtaba_bot_portal import mojtaba_bot_portal


class MojtabaSiteEntryTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def _get(self, authenticated=False):
        request = self.factory.get("/mojtaba.bot.ai/")
        request.user = (
            SimpleNamespace(is_authenticated=True, is_active=True)
            if authenticated else AnonymousUser()
        )
        return mojtaba_bot_portal(request)

    def test_public_seo_has_exact_canonical_but_no_private_content(self):
        """Allow indexing of public Starter30 copy without exposing owner chat."""
        with patch("prop_firm.starter30_live.release_is_open", return_value=False):
            response = self._get(authenticated=False)
        body = response.content.decode()
        self.assertEqual(response.status_code, 200)
        self.assertIn('<meta name="robots" content="index,follow', body)
        self.assertIn('<link rel="canonical" href="https://mojplaywin.com/mojtaba.bot.ai/">', body)
        self.assertEqual(body.count('rel="canonical"'), 1)
        self.assertNotIn("noindex", body)
        self.assertIn("simulated Moj Prop Starter30", body)
        self.assertNotIn('id="chat-form"', body)
        self.assertNotIn("csrf_for_chat", body)
        self.assertNotIn("OPENAI_API_KEY", body)
        self.assertNotIn('href="/mojprop-starter30-checkout/"', body)

    def test_untrusted_old_release_flag_cannot_advertise_payment_on_bot_portal(self):
        with patch("prop_firm.starter30_live.release_is_open", return_value=True) as release, \
             patch("prop_firm.starter30_live.verify_pre_invoice_configuration") as preflight:
            response = self._get(authenticated=False)
        body = response.content.decode()
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('href="/mojprop-starter30-checkout/"', body)
        self.assertIn('href="/moj-prop/starter-30-trx/"', body)
        self.assertIn("not a real-money investment", body)
        self.assertIn("Do not send TRX", body)
        self.assertIn("Passing a challenge or earning profit is not guaranteed", body)
        release.assert_not_called()
        preflight.assert_not_called()
        self.assertNotIn('id="chat-form"', body)

    def test_closed_payment_release_never_advertises_checkout(self):
        with patch("prop_firm.starter30_live.release_is_open", return_value=False), \
             patch("prop_firm.starter30_live.verify_pre_invoice_configuration") as preflight:
            body = self._get(authenticated=False).content.decode()
        preflight.assert_not_called()
        self.assertNotIn('href="/mojprop-starter30-checkout/"', body)
        self.assertIn("/moj-prop-intake/?format=html&amp;service=blueprint", body)

    def test_payment_preflight_exception_fails_closed_without_side_effect(self):
        with patch("prop_firm.starter30_live.release_is_open", return_value=True), \
             patch("prop_firm.starter30_live.verify_pre_invoice_configuration",
                   side_effect=RuntimeError("provider not ready")):
            response = self._get(authenticated=False)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('href="/mojprop-starter30-checkout/"',
                         response.content.decode())
        self.assertIn('href="/moj-prop/starter-30-trx/"',
                      response.content.decode())

    def test_canonical_path_resolves_without_separate_dns(self):
        self.assertEqual(reverse("mojtaba_bot_portal"), "/mojtaba.bot.ai/")
        self.assertEqual(
            resolve("/mojtaba.bot.ai/").func, mojtaba_bot_portal
        )

    def test_public_visitor_sees_inquiry_but_no_chat_form(self):
        response = self._get(authenticated=False)
        body = response.content.decode()
        self.assertEqual(response.status_code, 200)
        self.assertIn("Mojtaba.bot.ai", body)
        self.assertIn("/moj-prop-intake/?format=html&amp;service=blueprint", body)
        self.assertIn("/admin/login/?next=/mojtaba.bot.ai/", body)
        self.assertNotIn('id="chat-form"', body)
        self.assertNotIn('id="chat-message"', body)
        self.assertNotIn('var csrf = "', body)
        self.assertNotIn("OPENAI_API_KEY", body)
        self.assertNotIn("wallet transfer", body.lower().replace("no wallet transfer", ""))

    def test_public_search_engines_can_index_only_public_service_copy(self):
        with patch("prop_firm.starter30_live.release_is_open", return_value=False):
            response = self._get(authenticated=False)
        body = response.content.decode()
        self.assertIn('<meta name="robots" content="index,follow', body)
        self.assertIn('<link rel="canonical" href="https://mojplaywin.com/mojtaba.bot.ai/">', body)
        self.assertNotIn('<meta name="robots" content="noindex,', body)
        self.assertNotIn("X-Robots-Tag", response)
        self.assertNotIn('id="chat-form"', body)

    def test_authenticated_operator_chat_is_never_indexable(self):
        with patch("prop_firm.starter30_live.release_is_open", return_value=False):
            response = self._get(authenticated=True)
        body = response.content.decode()
        self.assertEqual(response.status_code, 200)
        self.assertIn('<meta name="robots" content="noindex,nofollow,noarchive">', body)
        self.assertNotIn('<meta name="robots" content="index,follow', body)
        self.assertNotIn('rel="canonical"', body)
        self.assertEqual(response["X-Robots-Tag"], "noindex, nofollow, noarchive")
        self.assertIn('id="chat-form"', body)

    def test_inactive_operator_sees_public_nonprivileged_page(self):
        request = self.factory.get("/mojtaba.bot.ai/")
        request.user = SimpleNamespace(is_authenticated=True, is_active=False)
        with patch("prop_firm.starter30_live.release_is_open", return_value=False):
            response = mojtaba_bot_portal(request)
        body = response.content.decode()
        self.assertIn('<meta name="robots" content="index,follow', body)
        self.assertNotIn('id="chat-form"', body)
        self.assertNotIn("X-Robots-Tag", response)

    def test_authenticated_user_gets_session_only_chat_shell(self):
        response = self._get(authenticated=True)
        body = response.content.decode()
        self.assertEqual(response.status_code, 200)
        self.assertIn('id="chat-form"', body)
        self.assertIn('id="chat-message"', body)
        self.assertIn('method="post" action="/api/master-chat/"', body)
        self.assertIn('credentials: "same-origin"', body)
        self.assertIn('result.reply', body)
        self.assertIn('content.textContent', body)
        self.assertNotIn('innerHTML', body)
        self.assertNotIn("OPENAI_API_KEY", body)
        self.assertEqual(response["X-Frame-Options"], "DENY")

    def test_request_nonce_is_in_csp_and_inline_resources(self):
        first = self._get(authenticated=True)
        second = self._get(authenticated=True)
        match = re.search(r'<script nonce="([^"]+)"', first.content.decode())
        self.assertIsNotNone(match)
        nonce = match.group(1)
        self.assertIn("script-src 'nonce-" + nonce + "'", first["Content-Security-Policy"])
        self.assertIn("style-src 'nonce-" + nonce + "'", first["Content-Security-Policy"])
        self.assertIn('style nonce="' + nonce + '"', first.content.decode())
        self.assertNotIn(nonce, second["Content-Security-Policy"])
        self.assertIn("no-store", first["Cache-Control"].lower())
        self.assertEqual(first["Referrer-Policy"], "same-origin")

    def test_portal_itself_never_accepts_mutating_requests(self):
        for method in ("post", "put", "patch", "delete"):
            with self.subTest(method=method):
                request = getattr(self.factory, method)("/mojtaba.bot.ai/")
                request.user = AnonymousUser()
                response = mojtaba_bot_portal(request)
                self.assertEqual(response.status_code, 405)
                self.assertIn("GET", response["Allow"])

    def test_inactive_user_does_not_receive_chat_interface(self):
        request = self.factory.get("/mojtaba.bot.ai/")
        request.user = SimpleNamespace(is_authenticated=True, is_active=False)
        body = mojtaba_bot_portal(request).content.decode()
        self.assertNotIn('id="chat-form"', body)
