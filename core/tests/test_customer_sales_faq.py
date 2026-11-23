"""Realistic offline product guidance without fabricated billing success."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.chat_runtime import MasterAgentChat
from core.customer_sales_faq import (
    MOJ_PROP_URL, MOJ_PROP_TERMS_REQUEST_URL, MOJ_SIGNALS_URL,
    MOJ_SIGNALS_REQUEST_URL, MOJ_STORE_URL,
    local_sales_answer,
)
from core.models import ApprovalRequest, ChatMessage, ChatSession


class SalesReplyUnitTests(TestCase):
    def test_english_moj_prop_price_discloses_simulation_and_invoice_safety(self):
        reply = local_sales_answer("How much does MOJ PROP Starter30 cost?")
        self.assertIn("30 TRX", reply)
        self.assertIn("simulated", reply)
        self.assertIn("Do not send TRX", reply)
        self.assertIn(MOJ_PROP_URL, reply)
        self.assertIn(MOJ_PROP_TERMS_REQUEST_URL, reply)
        self.assertNotIn("payment confirmed", reply.lower())

    def test_persian_prop_supports_arabic_yeh_and_zwnj(self):
        reply = local_sales_answer("قیمت چالش مج‌پراپ چيست؟")
        self.assertIn("۳۰ TRX", reply)
        self.assertIn("شبیه‌سازی", reply)
        self.assertIn("هیچ TRX ارسال نکنید", reply)
        self.assertIn(MOJ_PROP_TERMS_REQUEST_URL, reply)

    def test_signals_not_claimed_active(self):
        reply = local_sales_answer("Where do I find trading signals?")
        self.assertIn(MOJ_SIGNALS_URL, reply)
        self.assertIn(MOJ_SIGNALS_REQUEST_URL, reply)
        self.assertIn("not been verified", reply)
        self.assertNotIn("guaranteed", reply.lower())

    def test_store_does_not_claim_fulfillment(self):
        reply = local_sales_answer("فروشگاه محصولات دیجیتال کجاست؟")
        self.assertIn(MOJ_STORE_URL, reply)
        self.assertIn("باید", reply)

    def test_unrelated_or_oversized_message_does_not_invent_specific_answer(self):
        self.assertIsNone(local_sales_answer("سلام"))
        self.assertIsNone(local_sales_answer("x" * 2001))


class SalesReplyChatIntegrationTests(TestCase):
    def test_customer_receives_useful_link_and_no_external_model_call(self):
        user = get_user_model().objects.create_user("sales-faq-customer", password="test-pass")
        session = ChatSession.objects.create(user=user, title="MOJ PROP information")
        with patch.dict("os.environ", {"OPENAI_API_KEY": "present-but-not-authorized"}), patch("openai.OpenAI") as model:
            reply = MasterAgentChat().respond(session, "MOJ PROP challenge details")
        model.assert_not_called()
        self.assertIn(MOJ_PROP_URL, reply)
        self.assertIn(MOJ_PROP_TERMS_REQUEST_URL, reply)
        self.assertIn("Do not send TRX", reply)
        answer = ChatMessage.objects.get(session=session, role="assistant")
        self.assertEqual(answer.metadata["execution"], "local_sales_navigation")
        self.assertFalse(answer.metadata["llm_called"])
        self.assertFalse(ApprovalRequest.objects.exists())
