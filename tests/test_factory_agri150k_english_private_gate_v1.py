import importlib.util
from pathlib import Path
import tempfile
import unittest

MODULE = Path(__file__).resolve().parents[1] / "scripts/factory_agri150k_english_private_gate_v1.py"
spec = importlib.util.spec_from_file_location("agri150k_gate", MODULE)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class Agri150kPrivateGateTests(unittest.TestCase):
    def test_english_first_title_and_no_auto_release(self):
        p = gate.plan()
        self.assertEqual(p["product_id"], "AGRI-001")
        self.assertEqual(p["language"], "en-US")
        self.assertEqual(p["storefront"], "mojplaywin.com")
        self.assertEqual(len(p["chapters"]), 30)
        self.assertGreater(p["minimum_original_prose_words"], 150000)
        self.assertGreater(p["target_original_prose_words"], 150000)
        self.assertFalse(p["publication_allowed"])
        self.assertTrue(p["requires_independent_qc1000"])

    def test_existing_100k_contract_cannot_pass(self):
        chunks = ["## Chapter\n\n" + ("Distinct diagnosis terms " * 1700) for _ in range(20)]
        with self.assertRaisesRegex(ValueError, "REQUIRE_30"):
            gate.audit(chunks)
        chunks += ["Different diagnostic scope " * 1700 for _ in range(10)]
        result = gate.audit(chunks)
        self.assertIn("P0_UNDER_150001_ORIGINAL_WORDS", result["mechanical_findings"])
        self.assertFalse(result["publication_allowed"])

    def test_repeated_160k_draft_is_rejected(self):
        repeated = "This repeated generic paragraph is not evidence of real diagnostic teaching. " * 550
        result = gate.audit([repeated for _ in range(30)])
        self.assertGreater(result["original_prose_words_unreviewed"], 150000)
        self.assertIn("P0_REPETITION_OR_PADDING", result["mechanical_findings"])
        self.assertFalse(result["qc1000_approved"])

    def test_no_private_factory_no_side_effect(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError, "PRIVATE_FACTORY_AREA_NOT_ACCESSIBLE"):
                gate.install_private(d)


if __name__ == "__main__":
    unittest.main()
