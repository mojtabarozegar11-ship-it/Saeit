"""Offline C-01 commerce release gate regression tests; no network or real sale."""
import hashlib
import tempfile
import unittest
import zipfile
from pathlib import Path
from scripts.c01_release_gate import RELEASE_REFS, assess


class ReleaseGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.word = self.root / "volume.docx"
        self.pdf = self.root / "volume.pdf"
        with zipfile.ZipFile(self.word, "w") as doc:
            doc.writestr("[Content_Types].xml", "<Types/>")
            doc.writestr("word/document.xml", "<document/>")
        self.pdf.write_bytes(b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\n%%EOF\n")
        self.manifest = {
            "package_id": "MUSHROOM-EN-PRIVATE",
            "artifacts": {
                "docx": {"path": self.word.name, "sha256": hashlib.sha256(self.word.read_bytes()).hexdigest()},
                "pdf": {"path": self.pdf.name, "sha256": hashlib.sha256(self.pdf.read_bytes()).hexdigest()},
            },
            "evidence": {key: "private-evidence-reference-001" for key in (
                "rights_review_ref", "scientific_review_ref", "author_approval_ref", *RELEASE_REFS
            )},
        }

    def test_all_documented_preflight_still_never_certifies_live(self):
        result = assess(self.manifest, self.root)
        self.assertTrue(result["commerce_preflight_ready"])
        self.assertTrue(result["states"]["PRIVATE_READY"])
        self.assertTrue(result["states"]["AUTHOR_APPROVED"])
        self.assertFalse(result["states"]["STORE_LIVE_VERIFIED"])
        self.assertFalse(result["states"]["JOURNAL_SUBMITTED_RECEIPT"])
        self.assertEqual(result["missing_checks"], [])

    def test_missing_backup_blocks(self):
        del self.manifest["evidence"]["offhost_restore_ref"]
        result = assess(self.manifest, self.root)
        self.assertTrue(result["states"]["BLOCKED"])
        self.assertIn("offhost_restore_ref", result["missing_checks"])

    def test_missing_author_blocks_commerce_not_private_package(self):
        del self.manifest["evidence"]["author_approval_ref"]
        result = assess(self.manifest, self.root)
        self.assertTrue(result["states"]["PRIVATE_READY"])
        self.assertFalse(result["states"]["AUTHOR_APPROVED"])
        self.assertTrue(result["states"]["BLOCKED"])

    def test_invalid_word_file_blocks_even_with_matching_sha(self):
        self.word.write_bytes(b"not a docx")
        self.manifest["artifacts"]["docx"]["sha256"] = hashlib.sha256(self.word.read_bytes()).hexdigest()
        self.assertFalse(assess(self.manifest, self.root)["checks"]["word_sha256"])

    def test_invalid_pdf_file_blocks_even_with_matching_sha(self):
        self.pdf.write_bytes(b"not a pdf")
        self.manifest["artifacts"]["pdf"]["sha256"] = hashlib.sha256(self.pdf.read_bytes()).hexdigest()
        self.assertFalse(assess(self.manifest, self.root)["checks"]["pdf_sha256"])

    def test_changed_pdf_blocks(self):
        self.pdf.write_bytes(b"tampered")
        self.assertFalse(assess(self.manifest, self.root)["checks"]["pdf_sha256"])

    def test_path_traversal_blocks(self):
        self.manifest["artifacts"]["pdf"]["path"] = "../volume.pdf"
        self.assertFalse(assess(self.manifest, self.root)["checks"]["pdf_sha256"])

    def test_boolean_evidence_never_passes(self):
        self.manifest["evidence"]["rights_review_ref"] = True
        self.assertTrue(assess(self.manifest, self.root)["states"]["BLOCKED"])

    def test_no_side_effects(self):
        before = sorted(p.name for p in self.root.iterdir())
        assess(self.manifest, self.root)
        self.assertEqual(before, sorted(p.name for p in self.root.iterdir()))


if __name__ == "__main__":
    unittest.main()
