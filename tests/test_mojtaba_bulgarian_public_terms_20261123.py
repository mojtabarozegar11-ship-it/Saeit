"""Regression: public Bulgarian Starter30 guidance is truthful, static and GET-only.

No external API, finance execution, customer email, DB write or paid plan.
"""
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, SimpleTestCase

from core.customer_sales_faq import local_sales_answer
from core.mojtaba_bot_portal import mojtaba_bot_portal


class BulgarianStarter30GuideTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def _public(self, topic="prop-bg"):
        request = self.factory.get("/mojtaba.bot.ai/", {"topic": topic})
        request.user = AnonymousUser()
        with patch("openai.OpenAI") as model:
            response = mojtaba_bot_portal(request)
        model.assert_not_called()
        return response

    def test_bulgarian_price_question_is_answered_without_wallet_transfer(self):
        for text in ("Колко струва Moj Prop?", "Starter30 цена и такса", "MOJ PROP как да платя?"):
            with self.subTest(text=text):
                answer = local_sales_answer(text)
                self.assertIsNotNone(answer)
                self.assertIn("30 TRX", answer)
                self.assertIn("1 000 USD", answer)
                self.assertIn("100 000 USD", answer)
                self.assertIn("симулирано", answer)
                self.assertIn("НЕ изпращайте TRX", answer)
                self.assertIn("mojplaywin.com/moj-prop/", answer)
                self.assertIn("mojplaywin.com/moj-prop-intake/", answer)
                self.assertNotIn("https://mojtaba.bot.ai/", answer)
                self.assertNotIn("guaranteed", answer.casefold())

    def test_english_and_persian_and_other_queries_unchanged(self):
        english = local_sales_answer("MOJ PROP Starter30")
        persian = local_sales_answer("قیمت مج پراپ؟")
        self.assertIn("entry price is 30 TRX", english)
        self.assertIn("$1,000 virtual starting balance", english)
        self.assertIn("up to $100,000", english)
        self.assertIn("not guaranteed", english)
        self.assertIn("Do not send TRX until", english)
        self.assertIn("۳۰ TRX", persian)
        self.assertIn("۱٬۰۰۰ دلار مجازی", persian)
        self.assertIn("۱۰۰٬۰۰۰ دلار", persian)
        self.assertIn("هیچ TRX ارسال نکنید", persian)
        self.assertIsNone(local_sales_answer("колко струва нещо друго"))
        self.assertIsNone(local_sales_answer("взлом на чужд телефон"))
        self.assertIsNone(local_sales_answer("Moj Prop цена " + ("x" * 2100)))
        self.assertIn("entry price is 30 TRX", local_sales_answer("Moj Prop"))
        # The plain English commercial guide is still available by the exact
        # original portal topic, even when the public Bulgarian topic is added.

    def test_public_bulgarian_topic_get_renders_escaped_content_without_api(self):
        response = self._public()
        self.assertEqual(response.status_code, 200)
        body = response.content.decode("utf-8")
        self.assertIn('id="public-answer"', body)
        self.assertIn('lang="bg"', body)
        self.assertIn("30 TRX", body)
        self.assertIn("100 000 USD", body)
        self.assertIn("НЕ изпращайте TRX", body)
        self.assertIn('aria-current="true"', body)
        self.assertNotIn('id="chat-form"', body)
        self.assertNotIn('id="chat-message"', body)
        self.assertIn("no-store", response["Cache-Control"].lower())
        self.assertEqual(response["X-Frame-Options"], "DENY")
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertIn("default-src 'none'", response["Content-Security-Policy"])

    def test_unrecognized_topics_cannot_create_public_chat_or_leak_prompt(self):
        for topic in ("bg", "price", "prop-bg-private", "../admin", "prop-bg;admin", "Moj Prop цена", "х" * 2048):
            with self.subTest(topic=topic[:32]):
                response = self._public(topic)
                body = response.content.decode("utf-8")
                self.assertEqual(response.status_code, 200)
                self.assertNotIn('id="public-answer"', body)
                self.assertNotIn('id="chat-form"', body)

    def test_public_post_is_forbidden_even_for_approved_topic(self):
        request = self.factory.post("/mojtaba.bot.ai/", {"topic": "prop-bg", "email": "buyer@example.invalid"})
        request.user = AnonymousUser()
        with patch("openai.OpenAI") as model:
            response = mojtaba_bot_portal(request)
        model.assert_not_called()
        self.assertEqual(response.status_code, 405)
        self.assertEqual(response["Allow"], "GET")

    def test_route_and_content_ownership_remain_on_single_bot(self):
        src = Path(__file__).resolve().parents[1] / "core/mojtaba_bot_portal.py"
        body = src.read_text(encoding="utf-8")
        self.assertIn('"prop-bg": "Moj Prop цена"', body)
        self.assertIn('local_sales_answer(prompt) if prompt else None', body)
        self.assertNotIn("requests.post(", body)
