"""Guard single identity across conversation, economic, factory and defense."""
import unittest
from mojtaba_identity import BOT_ID, BOT_NAME
from ava_core.identity import BOT_ID as CORE_ID
from core.bot_identity import BOT_ID as SECURITY_ID, BOT_NAME as SECURITY_NAME
from core.unified_bot_identity import BOT_CODE, BOT_NAME as ECONOMIC_NAME

class CanonicalIdentityTests(unittest.TestCase):
    def test_shared_identity(self):
        self.assertEqual(BOT_ID, "mojtaba.bot.ai")
        self.assertEqual((CORE_ID, SECURITY_ID), (BOT_ID, BOT_ID))
        self.assertEqual((SECURITY_NAME, ECONOMIC_NAME), (BOT_NAME, BOT_NAME))

    def test_internal_db_slug_is_not_public_identity(self):
        self.assertEqual(BOT_CODE, "mojtaba-bot-ai")
        self.assertNotEqual(BOT_CODE, BOT_ID)

if __name__ == "__main__":
    unittest.main()
