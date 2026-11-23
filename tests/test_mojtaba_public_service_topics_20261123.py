"""Public Mojtaba.bot.ai service topics: zero cost, no privileged API or DB writes."""
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import urlencode

from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, SimpleTestCase

from core.mojtaba_bot_portal import mojtaba_bot_portal


class PublicMojtabaServiceTopicsTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def _get(self, topic=None, authenticated=False):
        path = "/mojtaba.bot.ai/"
        if topic is not None:
            path += "?" + urlencode({"topic": topic})
        request = self.factory.get(path)
        request.user = (
            SimpleNamespace(is_authenticated=True, is_active=True)
            if authenticated else AnonymousUser()
        )
        return mojtaba_bot_portal(request)

    def test_guest_can_read_prop_terms_without_private_chat_or_billable_calls(self):
        with patch("openai.OpenAI") as model:
            response = self._get("prop")
        model.assert_not_called()
        body = response.content.decode()
        self.assertEqual(response.status_code, 200)
        self.assertIn('id="public-answer"', body)
        self.assertIn("MOJ PROP offers a simulated trading challenge", body)
        self.assertIn("30 TRX", body)
        self.assertIn("Do not send TRX", body)
        self.assertIn("Free written terms request", body)
        self.assertNotIn('id="chat-form"', body)
        self.assertNotIn('id="chat-message"', body)
        self.assertNotIn("OPENAI_API_KEY", body)
        self.assertNotIn("noindex", body)
        self.assertEqual(response["X-Frame-Options"], "DENY")
        self.assertIn("no-store", response["Cache-Control"].lower())

    def test_guest_signal_topic_has_verified_unpaid_request_path(self):
        body = self._get("signals").content.decode()
        self.assertIn('id="public-answer"', body)
        self.assertIn("trading-signal information page", body)
        self.assertIn("/moj-prop-intake/?format=html&amp;service=signals", body)
        self.assertIn("do not pay without a valid server invoice", body)
        self.assertNotIn('id="chat-form"', body)

    def test_guest_store_topic_never_claims_fulfilled_payment(self):
        body = self._get("store").content.decode()
        self.assertIn('id="public-answer"', body)
        self.assertIn("https://mojplaywin.com/store/", body)
        self.assertIn("must each be confirmed by the store", body)
        self.assertNotIn("Payment confirmed", body)

    def test_unknown_topic_is_ignored_and_never_reaches_local_qa(self):
        for topic in ("", "administrator", "trade", "<script>alert(1)</script>", "prop;owner", "x" * 4096):
            with self.subTest(topic=topic[:32]), patch(
                "core.mojtaba_bot_portal.local_sales_answer",
                side_effect=AssertionError("unapproved public prompt evaluated"),
            ) as answer:
                body = self._get(topic).content.decode()
            answer.assert_not_called()
            self.assertNotIn('id="public-answer"', body)
            self.assertNotIn("<script>alert(1)</script>", body)
            self.assertNotIn('id="chat-form"', body)

    def test_public_guide_does_not_bypass_signed_in_protected_chat(self):
        body = self._get("prop", authenticated=True).content.decode()
        self.assertIn('id="public-answer"', body)
        self.assertIn('id="chat-form"', body)
        self.assertIn('method="post" action="/api/master-chat/"', body)
        self.assertIn('<meta name="robots" content="noindex,nofollow,noarchive">', body)

    def test_topic_links_remain_same_origin_and_disclose_no_payment(self):
        body = self._get().content.decode()
        self.assertIn('href="?topic=prop#public-help"', body)
        self.assertIn('href="?topic=signals#public-help"', body)
        self.assertIn('href="?topic=store#public-help"', body)
        self.assertNotIn('id="public-answer"', body)
        self.assertIn("No question, customer profile or wallet information is submitted.", body)

    def test_no_public_post_endpoint_created(self):
        request = self.factory.post("/mojtaba.bot.ai/", {"topic": "prop"})
        request.user = AnonymousUser()
        response = mojtaba_bot_portal(request)
        self.assertEqual(response.status_code, 405)
        self.assertIn("GET", response["Allow"])
