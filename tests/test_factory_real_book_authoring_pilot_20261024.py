#!/usr/bin/env python3
"""Offline tests: never call a real paid model or modify a public website."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

SOURCE = Path(__file__).resolve().parents[1] / "scripts/factory_real_book_authoring_pilot_20261024.py"
spec = importlib.util.spec_from_file_location("factory_author_pilot", SOURCE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class RealAuthoringTests(unittest.TestCase):
    def test_identity_and_prose_words(self):
        self.assertIsNotNone(mod.BOOK_ID.fullmatch("AGRI-001"))
        self.assertIsNone(mod.BOOK_ID.fullmatch("../AGRI-001"))
        self.assertIsNotNone(mod.CHUNK_NAME.fullmatch("chapter-01-part-001.md"))
        self.assertEqual(len(mod.tokens("## title\n\nThis book delivers actual practice.")), 5)

    def test_repeated_padding_rejected(self):
        text = ("This passage repeats an identical generic paragraph with no "
                "valuable original new information and no real original exercises.\n\n") * 100
        passed, reason = mod.distinct_enough(text, "")
        self.assertFalse(passed)
        self.assertIn(reason, ("CHUNK_LEXICAL_PADDING", "CHUNK_REPETITIVE"))

    def test_fake_original_text_can_pass_mechanical_screen_only(self):
        # Mechanically different dummy text is still NOT scientific quality.
        text = " ".join("researchconcept" + str(i) for i in range(900))
        passed, reason = mod.distinct_enough(text, "")
        self.assertTrue(passed)
        self.assertEqual(reason, "DRAFT_ONLY_NOT_SCIENTIFIC_QC")

    def fixture_root(self, tmp):
        area = Path(tmp) / "production-instructions"
        books = area / "stage-05/doctoral-monographs-100k-v1/plans"
        books.mkdir(parents=True)
        sources = area / "stage-02/source-evidence"
        sources.mkdir(parents=True)
        plan = {"id": "AGRI-001", "selling_title": "Sample Original Research Text",
                "selling_locale": "en-US", "chapters_required": 20,
                "minimum_original_prose_words": 100000,
                "quality1000_approved": False,
                "chapter_work_units": [{"number": i, "focus": "Original focused chapter"}
                                       for i in range(1, 21)]}
        (books / "AGRI-001.json").write_text(json.dumps(plan), encoding="utf8")
        (sources / "AGRI-001--r001.json").write_text(
            json.dumps({"schema": "test-source-provenance", "sources": []}), encoding="utf8")
        return area

    def test_preflight_never_calls_network_or_sells(self):
        import argparse
        with tempfile.TemporaryDirectory() as tmp:
            self.fixture_root(tmp)
            opts = argparse.Namespace(factory_private=tmp, product="AGRI-001",
                     api_key_file=str(Path(tmp)/"nonexistent-key"),
                     execute=False, max_total_usd=0, input_usd_per_million=0,
                     output_usd_per_million=0, max_output_tokens=5000,
                     model="gpt-5-mini")
            with mock.patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
                with mock.patch.object(mod, "call_model") as call:
                    result = mod.run(opts)
            call.assert_not_called()
            self.assertEqual(result["state"], "PREFLIGHT_ONLY_NO_CHARGE")
            self.assertEqual(result["draft_words_so_far"], 0)
            self.assertFalse(result["api_credential_available"])
            self.assertFalse(result["published"])

    def test_no_key_no_external_charges(self):
        import argparse
        with tempfile.TemporaryDirectory() as tmp:
            self.fixture_root(tmp)
            opts = argparse.Namespace(factory_private=tmp, product="AGRI-001",
                     api_key_file=str(Path(tmp)/"absent"),
                     execute=True, max_total_usd=1, input_usd_per_million=1,
                     output_usd_per_million=1, max_output_tokens=5000,
                     model="gpt-5-mini")
            with mock.patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
                with mock.patch.object(mod, "call_model") as call:
                    with self.assertRaisesRegex(ValueError, "CREDENTIAL_UNAVAILABLE"):
                        mod.run(opts)
            call.assert_not_called()

    def test_parse_mocked_responses_api_usage(self):
        content = {"id": "resp-test", "output": [
            {"type": "message", "content": [
                {"type": "output_text", "text": "Original academic sample."}]}],
            "usage": {"input_tokens": 13, "output_tokens": 7}}
        class MockResponse:
            def __enter__(self): return self
            def __exit__(self, exc_type, exc, tb): pass
            def read(self, _: int): return json.dumps(content).encode()
        with mock.patch.object(mod.urllib.request, "urlopen", return_value=MockResponse()):
            text, usage, ident = mod.call_model("private-test-key", "gpt-5-mini", "Prompt", 5000)
        self.assertEqual(text, "Original academic sample.")
        self.assertEqual(usage["input_tokens"], 13)
        self.assertEqual(ident, "resp-test")


if __name__ == "__main__":
    unittest.main()
