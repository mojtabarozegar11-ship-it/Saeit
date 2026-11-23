"""No customer prompt may incur a paid model call merely because a key exists."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.chat_runtime import MasterAgentChat
from core.models import ApprovalRequest, ChatMessage, ChatSession


class ApiFreeMasterChatTests(TestCase):
    def setUp(self):
        self.customer = get_user_model().objects.create_user(
            username="api-free-customer", password="test-only-password",
        )
        self.session = ChatSession.objects.create(user=self.customer, title="Customer questions")

    def test_customer_general_chat_ignores_configured_paid_model_credentials(self):
        env = {"OPENAI_API_KEY": "test-key-not-an-approval", "OPENAI_CHAT_MODEL": "gpt-6"}
        with patch.dict("os.environ", env), patch("openai.OpenAI") as client:
            reply = MasterAgentChat().respond(self.session, "سلام درباره خدمات بیشتر توضیح بده")
        client.assert_not_called()
        self.assertIn("مجوز اختصاصی ندارد", reply)
        self.assertIn("هیچ اقدامی اجرا نشد", reply)
        msg = ChatMessage.objects.get(session=self.session, role="assistant")
        self.assertEqual(msg.metadata["execution"], "local_no_external_ai_api")
        self.assertFalse(msg.metadata["llm_called"])
        self.assertEqual(ChatMessage.objects.filter(session=self.session).count(), 2)
        self.assertFalse(ApprovalRequest.objects.exists())

    def test_api_free_customer_chat_still_accepts_message_without_key(self):
        with patch.dict("os.environ", {}, clear=True), patch("openai.OpenAI") as client:
            reply = MasterAgentChat().respond(self.session, "درود به تیم پشتیبانی")
        client.assert_not_called()
        self.assertIn("پیام دریافت و ثبت شد", reply)
        self.assertFalse(
            ChatMessage.objects.get(session=self.session, role="assistant").metadata["llm_called"]
        )
