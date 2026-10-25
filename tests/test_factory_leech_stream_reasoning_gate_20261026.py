"""Regression tests: never accept leaked reasoning or a mismatched work order."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch


def load_module():
    path = Path(__file__).resolve().parents[1] / "scripts/factory_leech_vps_resource_guarded_author_20261025.py"
    spec = importlib.util.spec_from_file_location("leech_stream_operator", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def alpha(number):
    letters = []
    while True:
        number, remainder = divmod(number, 26)
        letters.append(chr(ord("a") + remainder))
        if not number:
            return "".join(reversed(letters))
        number -= 1


class LeechStreamAcceptanceRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.operator = load_module()
        cls.valid = " ".join("lexeme" + alpha(i) for i in range(320)) + "."

    def test_substantive_original_segment_is_structurally_eligible(self):
        self.assertTrue(self.operator.stream_segment_is_acceptable(self.valid))

    def test_streamed_reasoning_and_control_tokens_are_rejected(self):
        for marker in ("<think>hidden chain</think>", "<|im_start|>",
                       "<|im_end|>", "[INST]", "[/INST]"):
            with self.subTest(marker=marker):
                self.assertFalse(self.operator.stream_segment_is_acceptable(
                    marker + " " + self.valid))

    def test_short_repetitive_or_incomplete_text_is_rejected(self):
        for text in ("word " * 400 + ".", "Only a short sentence.", self.valid[:-1]):
            with self.subTest(text=text[:30]):
                self.assertFalse(self.operator.stream_segment_is_acceptable(text))

    def test_wrong_order_rejected_even_when_book_length_complete(self):
        fake = SimpleNamespace(stdout=json.dumps({
            "order_id": "WRONG-ORDER", "next_chapter": None}))
        with patch.object(self.operator.subprocess, "run", return_value=fake):
            with self.assertRaisesRegex(RuntimeError, "WRONG_PRODUCT_ORDER"):
                self.operator.assignment()


if __name__ == "__main__":
    unittest.main()
