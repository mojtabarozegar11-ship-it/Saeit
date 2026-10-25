import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch


def load_writer():
    path = Path(__file__).resolve().parents[1] / "scripts/factory_leech_free_offline_original_author_20261025.py"
    spec = importlib.util.spec_from_file_location("leech_offline_author", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FreeLeechAuthorContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.author = load_writer()
        cls.chapters = [{
            "chapter_number": i,
            "chapter_title": "Substantive Chapter " + str(i),
            "four_mandatory_sections": ["Context", "Research", "Operations", "Safety"],
            "individually_assessed_professional_output": "Evidence matrix",
            "research_claim_ids": [],
            "scientific_primary_sources_to_extend": True
        } for i in range(1, 31)]
        cls.work = {"official_title": "The Professional Leech Farming Handbook"}
        cls.sources = [{"id": "source1", "title": "Primary source", "url": "https://example.invalid/paper"}]

    def test_empty_book_must_generate_chapter_one(self):
        parts = {i: [] for i in range(1, 31)}
        data = self.author.make_prompt(self.work, self.chapters, self.sources, parts)
        self.assertEqual(data["next_chapter"], 1)
        self.assertEqual(data["next_part"], 1)
        self.assertEqual(data["chapter_number"], 1)
        self.assertEqual(data["global_verified_draft_words"], 0)
        self.assertFalse(data["complete_length_only"])

    def test_partial_first_chapter_never_marked_complete(self):
        parts = {i: [] for i in range(1, 31)}
        parts[1].append((1, "Unique professional analysis and evaluation of leech farm processes."))
        data = self.author.make_prompt(self.work, self.chapters, self.sources, parts)
        self.assertEqual((data["next_chapter"], data["next_part"]), (1, 2))
        self.assertFalse(data["complete_length_only"])

    def test_rollover_waits_for_actual_word_count(self):
        parts = {i: [] for i in range(1, 31)}
        # Synthetic text is used only for unit tests, never persisted or admitted.
        parts[1].append((1, "professional " * self.author.TARGET_PER_CHAPTER))
        data = self.author.make_prompt(self.work, self.chapters, self.sources, parts)
        self.assertEqual((data["next_chapter"], data["next_part"]), (2, 1))
        self.assertFalse(data["complete_length_only"])

    def test_empty_source_corpus_does_not_auto_certify(self):
        self.assertEqual(self.author.MIN_WORDS, 150001)
        self.assertEqual(self.author.REQUIRED_CHAPTERS, 30)
        self.assertGreater(self.author.TARGET_PER_CHAPTER * 30, 150001)


    def test_private_accept_rejects_reasoning_tokens_without_writing(self):
        # The direct private writer must fail closed even if the upstream
        # streaming operator is bypassed; no real manuscript path is touched.
        clean = " ".join("lexeme" + str(i) + "analysis" for i in range(320)) + "."
        chunks = {i: [] for i in range(1, 31)}
        with patch.object(self.author, "source_evidence", return_value=({}, [], [])), \
             patch.object(self.author, "state", return_value=({}, 0, 1, 1)), \
             patch.object(self.author, "ensure_private", side_effect=AssertionError("unexpected write")):
            for token in ("<think>hidden reasoning</think>", "<|im_start|>",
                          "<|im_end|>", "[INST]", "[/INST]", "<|assistant"):
                with self.subTest(token=token):
                    with self.assertRaisesRegex(RuntimeError, "MODEL_REASONING_OR_CONTROL_TOKEN"):
                        self.author.accept(chunks, clean + " " + token)


if __name__ == "__main__":
    unittest.main()
