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
                       "<|im_end|>", "<|assistant", "<|endoftext|>",
                       "[INST]", "[/INST]"):
            with self.subTest(marker=marker):
                self.assertFalse(self.operator.stream_segment_is_acceptable(
                    marker + " " + self.valid))

    def test_invisible_and_compatibility_controls_cannot_hide_reasoning(self):
        # The live streaming acceptance gate must reject these before any
        # private author 'accept' subprocess receives the generated text.
        disguised = (
            "<th\u200bink>internal reasoning</th\u200bink>",
            "<\uff54hink>hidden chain</\uff54hink>",
            "<th\u202eink>reversed control</th\u202eink>",
            "<th\u200eink>left-to-right mark",
            "<th\u200fink>right-to-left mark",
            "<th\u061cink>Arabic letter mark",
            "<|im_\u2060start|>",
            "<th\u034fink>combining grapheme joiner",
            "<th\ufe0fink>variation selector",
            "<th\U000E0100ink>supplementary variation selector",
            "[\uff29NST]",
        )
        for marker in disguised:
            with self.subTest(marker=repr(marker)):
                self.assertFalse(self.operator.stream_segment_is_acceptable(
                    marker + " " + self.valid))

    def test_endoftext_invisible_variants_rejected_by_both_gates(self):
        writer_path = Path(__file__).resolve().parents[1] / "scripts/factory_leech_free_offline_original_author_20261025.py"
        spec = importlib.util.spec_from_file_location("leech_endoftext_private_gate", writer_path)
        writer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(writer)
        for marker in ("<|endoftext|>", "<|endo\u200bftext|>",
                       "<|endof\u034ftext|>", "<|\uff45ndoftext|>"):
            with self.subTest(marker=repr(marker)):
                body = marker + " " + self.valid
                self.assertFalse(self.operator.stream_segment_is_acceptable(body))
                with patch.object(writer, "source_evidence", return_value=({}, [], [])):
                    with patch.object(writer, "state", return_value=({}, 0, 1, 1)):
                        with patch.object(writer, "ensure_private", side_effect=AssertionError("UNSAFE_WRITE_REACHED")):
                            with self.assertRaisesRegex(RuntimeError, "MODEL_REASONING_OR_CONTROL_TOKEN"):
                                writer.accept({1: []}, body)

    def test_private_accept_rejects_disguised_reasoning_before_file_writes(self):
        # The private accept command can be invoked independently of the
        # streaming operator; it must apply the same canonical safety gate.
        writer_path = Path(__file__).resolve().parents[1] / "scripts/factory_leech_free_offline_original_author_20261025.py"
        spec = importlib.util.spec_from_file_location("leech_private_accept_gate", writer_path)
        writer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(writer)
        disguised = (
            "<th\u200bink>private reasoning</th\u200bink>",
            "<\uff54hink>private reasoning</\uff54hink>",
            "<th\u202eink>private reasoning</th\u202eink>",
            "<th\u200eink>private reasoning",
            "<th\u200fink>private reasoning",
            "<th\u061cink>private reasoning",
            "<|im_\u2060start|>",
            "<th\u034fink>combining grapheme joiner",
            "<th\ufe0fink>variation selector",
            "<th\U000E0100ink>supplementary variation selector",
            "[\uff29NST]",
        )
        for marker in disguised:
            with self.subTest(marker=repr(marker)):
                body = marker + " " + self.valid
                with patch.object(writer, "source_evidence", return_value=({}, [], [])), \
                     patch.object(writer, "state", return_value=({}, 0, 1, 1)), \
                     patch.object(writer, "ensure_private", side_effect=AssertionError("UNSAFE_WRITE_REACHED")):
                    with self.assertRaisesRegex(RuntimeError, "MODEL_REASONING_OR_CONTROL_TOKEN"):
                        writer.accept({1: []}, body)

    def test_private_accept_rejects_unicode_disguised_placeholders_before_write(self):
        # The private author must never save citation placeholders disguised
        # by format controls or compatibility glyphs. The independent audit
        # is a second gate, not a substitute for pre-write validation.
        writer_path = Path(__file__).resolve().parents[1] / "scripts/factory_leech_free_offline_original_author_20261025.py"
        spec = importlib.util.spec_from_file_location("leech_placeholder_gate", writer_path)
        writer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(writer)
        disguised = (
            "[citation\u200b needed]",
            "lorem \u200bipsum",
            "as an a\u200ci language model",
            "[\uff49nsert missing source]",
            "this is a place\u200bholder",
            "[citation\u034f needed]",  # combining grapheme joiner, Mn
            "[citation\ufe0f needed]",  # variation selector-16, Mn
            "[citation\U000E0100 needed]",  # supplementary variation selector, Mn
            "this is a place\u2063holder",  # invisible separator, Cf
            "lorem \u180eipsum",  # Mongolian vowel separator, Cf
            "[citation\u2066 needed]",  # left-to-right isolate, Cf
            "bibliography\r\n",  # CRLF line ending must not evade gate
            "bibliography\u2028",  # Unicode line separator, Zl
            "bibliography\u0085",  # next-line control, Cc
            "as an ai\u202e language model",  # right-to-left override, Cf
            "\uff4c\uff4f\uff52\uff45\uff4d \uff49\uff50\uff53\uff55\uff4d",  # fullwidth NFKC compatibility
        )
        for marker in disguised:
            with self.subTest(marker=repr(marker)):
                with patch.object(writer, "source_evidence", return_value=({}, [], [])), \
                     patch.object(writer, "state", return_value=({}, 0, 1, 1)), \
                     patch.object(writer, "ensure_private",
                                  side_effect=AssertionError("UNSAFE_WRITE_REACHED")):
                    with self.assertRaisesRegex(RuntimeError, "CONTENT_INTEGRITY_MARKER"):
                        writer.accept({1: []}, marker + " " + self.valid)

    def test_short_repetitive_or_incomplete_text_is_rejected(self):
        for text in ("word " * 400 + ".", "Only a short sentence.", self.valid[:-1]):
            with self.subTest(text=text[:30]):
                self.assertFalse(self.operator.stream_segment_is_acceptable(text))

    def test_completed_writer_assignment_retains_order_identity(self):
        writer_path = Path(__file__).resolve().parents[1] / "scripts/factory_leech_free_offline_original_author_20261025.py"
        spec = importlib.util.spec_from_file_location("leech_private_writer", writer_path)
        writer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(writer)
        with patch.object(writer, "state", return_value=({}, writer.MIN_WORDS, None, None)):
            complete = writer.make_prompt({}, [], [], {})
        self.assertEqual(complete["order_id"], "WO-26102501")
        self.assertTrue(complete["complete_length_only"])
        self.assertIsNone(complete["next_chapter"])
        fake = SimpleNamespace(stdout=json.dumps(complete))
        with patch.object(self.operator.subprocess, "run", return_value=fake):
            self.assertEqual(self.operator.assignment(), complete)

    def test_wrong_order_rejected_even_when_book_length_complete(self):
        fake = SimpleNamespace(stdout=json.dumps({
            "order_id": "WRONG-ORDER", "next_chapter": None}))
        with patch.object(self.operator.subprocess, "run", return_value=fake):
            with self.assertRaisesRegex(RuntimeError, "WRONG_PRODUCT_ORDER"):
                self.operator.assignment()


if __name__ == "__main__":
    unittest.main()
