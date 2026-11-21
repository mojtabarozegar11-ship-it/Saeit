"""Regression tests for the MojPlayWin-hosted canonical assistant entry.

All tests are read-only: no model/API calls, payment, task scheduling or bot start.
"""
import re
from types import SimpleNamespace

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
