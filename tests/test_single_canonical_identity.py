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

    def test_owner_identity_rejected_consistently_in_all_subsystems(self):
        for invalid in (None, 4, "", " owner", "owner ", "owner\\\\nadmin",
                        "owner\\\\radmin", "owner\\\\x00admin", "owner\\nadmin",
                        "owner\\x00admin", "owner\\x7fadmin"):
            with self.subTest(identity=repr(invalid)):
                with self.assertRaises(ValueError):
                    validate_owner_id(invalid)
                with self.assertRaises(ValueError):
                    ConversationEngine(owner_id=invalid, brain=lambda _: "ok")
                with self.assertRaises(ValueError):
                    AutonomousGoalDirector(owner_id=invalid, proposer=lambda _: ())
                with self.assertRaises(ValueError):
                    CapabilityHub(owner_id=invalid)
                with self.assertRaises(ValueError):
                    ActionRequest("r", invalid, "module", "run", {})
                with self.assertRaises(ValueError):
                    AvaMemory().add(MemoryItem("id", invalid, "text", "now"))

    def test_accepted_owner_id_is_not_coerced(self):
        self.assertEqual(validate_owner_id("owner:external-42"), "owner:external-42")

if __name__ == "__main__":
    unittest.main()
