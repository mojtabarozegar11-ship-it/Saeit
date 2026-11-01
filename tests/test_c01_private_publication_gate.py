"""No external services, customer data, Django settings, or production DB needed."""
import hashlib
import hmac
import json
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from c01_private_publication_gate import GateError, evaluate, main


class PublicationGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        with zipfile.ZipFile(str(self.root / "volume.docx"), "w") as f:
            f.writestr("[Content_Types].xml", "<Types/>")
            f.writestr("word/document.xml", "<document/>")
        (self.root / "volume.pdf").write_bytes(b"%PDF-1.4\n1 0 obj\nendobj\n%%EOF\n")
        for key in ("review", "rights", "author"):
            (self.root / (key + ".txt")).write_text(key, encoding="utf-8")
        self.manifest = {
            "schema_version": 1, "kind": "book", "id": "MUSHROOM-EN-V1",
            "artifacts": {"docx": self.ref("volume.docx"), "pdf": self.ref("volume.pdf")},
            "evidence": {"review": {"decision": "passed", "file": self.ref("review.txt")},
                         "rights": {"decision": "cleared", "file": self.ref("rights.txt")}},
        }

    def ref(self, name):
        return {"path": name, "sha256": hashlib.sha256((self.root / name).read_bytes()).hexdigest()}

    def test_complete_private_package_not_live(self):
        result = evaluate(self.manifest, self.root)
        self.assertEqual(result["status"], "PRIVATE_READY")
        self.assertFalse(result["store_live_verified"])
        self.assertFalse(result["journal_submitted_receipt"])

    def signed_author_receipt(self, key):
        receipt = self.ref("author.txt")
        payload = json.dumps({"id": self.manifest["id"],
                              "docx": self.manifest["artifacts"]["docx"]["sha256"],
                              "pdf": self.manifest["artifacts"]["pdf"]["sha256"],
                              "approval_receipt": receipt["sha256"]},
                             sort_keys=True, separators=(",", ":")).encode("utf-8")
        self.manifest["evidence"]["author_approval"] = {
            "decision": "approved", "file": receipt,
            "hmac_sha256": hmac.new(key, payload, hashlib.sha256).hexdigest(),
        }

    def test_author_approval_requires_trusted_key(self):
        key = b"k" * 32
        self.signed_author_receipt(key)
        self.assertEqual(evaluate(self.manifest, self.root)["status"], "PRIVATE_READY")
        self.assertEqual(evaluate(self.manifest, self.root, approval_key=key)["status"], "AUTHOR_APPROVED")
        with self.assertRaisesRegex(GateError, "AUTHOR_APPROVAL_SIGNATURE_MISMATCH"):
            evaluate(self.manifest, self.root, approval_key=b"x" * 32)

    def test_no_rights_is_blocked(self):
        del self.manifest["evidence"]["rights"]
        self.assertEqual(evaluate(self.manifest, self.root)["status"], "BLOCKED")

    def test_wrong_review_decision_is_blocked(self):
        self.manifest["evidence"]["review"]["decision"] = "pending"
        self.assertEqual(evaluate(self.manifest, self.root)["status"], "BLOCKED")

    def test_corrupt_pdf_is_blocked(self):
        (self.root / "volume.pdf").write_bytes(b"NOT A PDF")
        self.manifest["artifacts"]["pdf"] = self.ref("volume.pdf")
        with self.assertRaisesRegex(GateError, "PDF_SIGNATURE_INVALID"):
            evaluate(self.manifest, self.root)

    def test_corrupt_docx_is_blocked(self):
        (self.root / "volume.docx").write_bytes(b"PK-not-a-docx")
        self.manifest["artifacts"]["docx"] = self.ref("volume.docx")
        with self.assertRaisesRegex(GateError, "DOCX_CONTAINER_INVALID"):
            evaluate(self.manifest, self.root)

    def test_digest_mismatch_is_blocked(self):
        self.manifest["artifacts"]["pdf"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(GateError, "SHA256_MISMATCH"):
            evaluate(self.manifest, self.root)

    def test_path_traversal_is_blocked(self):
        self.manifest["artifacts"]["pdf"]["path"] = "../secret.pdf"
        with self.assertRaisesRegex(GateError, "PATH_ESCAPE_BLOCKED"):
            evaluate(self.manifest, self.root)

    def test_symlink_is_blocked(self):
        (self.root / "linked.pdf").symlink_to(self.root / "volume.pdf")
        self.manifest["artifacts"]["pdf"]["path"] = "linked.pdf"
        with self.assertRaisesRegex(GateError, "SYMLINK_BLOCKED"):
            evaluate(self.manifest, self.root)

    def test_extra_evidence_is_rejected(self):
        self.manifest["evidence"]["payment"] = {"decision": "paid", "file": self.ref("author.txt")}
        with self.assertRaisesRegex(GateError, "EVIDENCE_SCHEMA_INVALID"):
            evaluate(self.manifest, self.root)

    def test_article_cannot_claim_submission(self):
        self.manifest["kind"] = "article"
        result = evaluate(self.manifest, self.root)
        self.assertEqual(result["status"], "PRIVATE_READY")
        self.assertFalse(result["journal_submitted_receipt"])

    def test_cli_fails_closed_and_does_not_modify_artifacts(self):
        path = self.root / "manifest.json"
        path.write_text(json.dumps(self.manifest), encoding="utf-8")
        before = {p.name: p.read_bytes() for p in self.root.iterdir() if p.is_file()}
        self.assertEqual(main([str(path), "--root", str(self.root)]), 0)
        self.manifest["evidence"].pop("review")
        path.write_text(json.dumps(self.manifest), encoding="utf-8")
        self.assertEqual(main([str(path), "--root", str(self.root)]), 2)
        for name, data in before.items():
            if name != "manifest.json":
                self.assertEqual((self.root / name).read_bytes(), data)


if __name__ == "__main__":
    unittest.main()
