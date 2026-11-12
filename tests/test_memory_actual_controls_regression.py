"""Regression coverage for actual control bytes, not escaped text literals."""
import unittest
from ava_core import Ava, ConsentError


class ActualControlByteRegression(unittest.TestCase):
    def test_actual_control_bytes_rejected_before_storage(self):
        bot = Ava(owner_id="owner-1", brain=lambda messages: "ok")
        for control in ("\x00", "\x01", "\x1b", "\x1f", "\x7f"):
            with self.subTest(control=ord(control)):
                with self.assertRaises(ValueError):
                    bot.remember("secret" + control + "tail", consent=True)
        self.assertEqual(bot.list_memories(), ())

    def test_failed_write_does_not_require_deletion(self):
        bot = Ava(owner_id="owner-1", brain=lambda messages: "ok")
        with self.assertRaises(ConsentError):
            bot.remember("secret\x00tail")
        self.assertEqual(bot.list_memories(), ())


if __name__ == "__main__":
    unittest.main()
