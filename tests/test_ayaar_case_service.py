"""Executable isolation, privacy, reviewer-gate and status tests for AYAR."""
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from core import ayaar_case_service as service
except ImportError:
    import ayaar_case_service as service


class FakeEvidence(io.BytesIO):
    def __init__(self, name, raw):
        super().__init__(raw)
        self.name = name
        self.size = len(raw)

    def chunks(self, chunk_size=65536):
        self.seek(0)
        while True:
            item = self.read(chunk_size)
            if not item:
                break
            yield item


def make_dossier(public=False):
    return {
        "category": "ebook", "service": "professional",
        "product_name": "Principles of Digital Economics",
        "product_version": "1.0", "product_url": "https://example.org/book",
        "email": "publisher@example.org",
        "scope": "Review originality, references, provenance and accessibility.",
        "evidence_summary": "Original content with author-approved publication rights",
        "rights_declared": True, "privacy_consent": True,
        "publication_consent": public,
    }


def make_review(conflict=False):
    return {
        "criteria": {
            key: {"score": 4 if not (key == "rights" and conflict) else 1,
                  "evidence": "Verified test record with versioned source reference"}
            for key, _, _ in service.RUBRICS["ebook"]
        },
        "independence_statement": "I am a qualified reviewer with no financial relationship to the publisher.",
        "review_scope": "Full EPUB and rights chain for version 1.0",
        "methodology_notes": "Cross-check author permissions, citations and reading accessibility.",
        "no_material_conflict": True,
        "publish_report": True,
    }


class CaseServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ayar-case-unit-")
        os.environ["AYAAR_CASE_TEST_DIR"] = self.temp.name
        self.addCleanup(lambda: os.environ.pop("AYAAR_CASE_TEST_DIR", None))
        self.addCleanup(self.temp.cleanup)
        self.secret = "test-django-secret-do-not-use-in-production"

    def create(self, public=False, uploads=None, address="192.0.2.45"):
        return service.create_case(make_dossier(public), uploads or [], address, self.secret)

    def test_private_receipt_and_status(self):
        item = self.create()
        self.assertTrue(item["case_id"].startswith("AYR-"))
        self.assertGreater(len(item["access_key"]), 30)
        record = service.case_status(item["case_id"], item["access_key"], self.secret)
        self.assertEqual(record["status"], "submitted")
        self.assertEqual(len(record["events"]), 1)
        self.assertNotIn("contact_email", record)
        with self.assertRaises(service.CaseError):
            service.case_status(item["case_id"], "incorrect-access-key", self.secret)

    def test_staff_queue_and_lifecycle(self):
        item = self.create(public=True)
        queue = service.staff_list()
        self.assertEqual(len(queue), 1)
        self.assertEqual(queue[0]['case_id'], item['case_id'])
        service.set_status(item["case_id"], "in_review", "staff:12", "Review began after triage")
        reviewed = service.submit_review(item["case_id"], "staff:12", make_review())
        self.assertEqual(reviewed["status"], "reviewed")
        self.assertAlmostEqual(reviewed["score"], 80.0)
        self.assertTrue(reviewed["public_report"])
        self.assertEqual(len(service.registry()), 1)
        user = service.case_status(item["case_id"], item["access_key"], self.secret)
        self.assertEqual(user["review"]["schema"], "AYAR-HUMAN-REVIEW-v1")
        self.assertEqual(len(user["review"]["criteria"]), 8)
        with self.assertRaises(service.CaseError):
            service.set_status(item["case_id"], "declined", "staff:12", "Cannot silently change completed result")

    def test_followup_after_staff_information_request(self):
        item = self.create()
        service.set_status(item["case_id"], "needs_information", "staff:8", "Please provide updated permissions")
        extra = FakeEvidence("permissions.txt", b"Updated publication authorization with version and scope")
        answer = service.append_case_evidence(
            item["case_id"], item["access_key"],
            "This is the renewed permissions record for version 1.0.", [extra], self.secret
        )
        self.assertEqual(answer["status"], "submitted")
        self.assertEqual(answer["attachments_added"], 1)
        tracked = service.case_status(item["case_id"], item["access_key"], self.secret)
        self.assertEqual(tracked["files"][0]["original_name"], "permissions.txt")
        self.assertEqual(tracked["events"][-1]["action"], "customer_followup")
        self.assertEqual(service.staff_list()[0]["file_count"], 1)

    def test_followup_access_and_status_are_enforced(self):
        item = self.create()
        with self.assertRaises(service.CaseError):
            service.append_case_evidence(item["case_id"], item["access_key"],
                                         "This is a premature case response", [], self.secret)
        service.set_status(item["case_id"], "needs_information", "staff:8", "Provide updated product tests")
        with self.assertRaises(service.CaseError):
            service.append_case_evidence(item["case_id"], "incorrect-key", "Updated product test observations", [], self.secret)
        service.append_case_evidence(item["case_id"], item["access_key"],
                                     "Updated reproducible testing notes attached in text", [], self.secret)
        self.assertEqual(service.case_status(item["case_id"], item["access_key"], self.secret)["status"], "submitted")
        service.submit_review(item["case_id"], "staff:8", make_review())
        with self.assertRaises(service.CaseError):
            service.append_case_evidence(item["case_id"], item["access_key"],
                                         "Do not silently amend signed findings", [], self.secret)

    def test_followup_attachment_quota_prevents_unbounded_growth(self):
        item = self.create()
        for cycle in range(4):
            service.set_status(item["case_id"], "needs_information", "staff:3", "More file provenance required")
            extra = [FakeEvidence("proof.txt", b"Evidence of rights and build provenance") for _ in range(3)]
            service.append_case_evidence(item["case_id"], item["access_key"],
                                         "Reply with three evidence documents, cycle %s" % cycle, extra, self.secret)
        service.set_status(item["case_id"], "needs_information", "staff:3", "Provide a fifth reply")
        with self.assertRaises(service.CaseError):
            service.append_case_evidence(item["case_id"], item["access_key"],
                                         "Additional unbounded attachment request", [FakeEvidence("extra.txt", b"xyz")], self.secret)
        self.assertEqual(len(service.staff_case(item["case_id"])["files"]), 12)

    def test_no_publication_without_consent(self):
        item = self.create(public=False)
        result = service.submit_review(item["case_id"], "staff:1", make_review())
        self.assertFalse(result["public_report"])
        self.assertEqual(service.registry(), [])

    def test_critical_criterion_override(self):
        item = self.create(public=True)
        result = service.submit_review(item["case_id"], "staff:1", make_review(conflict=True))
        self.assertEqual(result["grade"], "Critical gate failure")

    def test_conflicts_and_incomplete_evidence_are_blocked(self):
        item = self.create()
        review = make_review()
        review["no_material_conflict"] = False
        with self.assertRaises(service.CaseError):
            service.submit_review(item["case_id"], "staff:1", review)
        review = make_review()
        review["criteria"]["sources"]["evidence"] = "short"
        with self.assertRaises(service.CaseError):
            service.submit_review(item["case_id"], "staff:1", review)

    def test_private_file_access_and_owner_erasure(self):
        raw = b"%PDF-1.7\nexample controlled test evidence\n%%EOF"
        item = self.create(uploads=[FakeEvidence("review.pdf", raw)])
        stored = service.staff_case(item["case_id"])["files"]
        self.assertEqual(len(stored), 1)
        path, filename = service.staff_file(item["case_id"], stored[0]["id"])
        self.assertEqual(path.read_bytes(), raw)
        self.assertEqual(filename, "review.pdf")
        service.delete_case(item["case_id"], item["access_key"], self.secret)
        self.assertFalse(path.exists())
        with self.assertRaises(service.CaseError):
            service.case_status(item["case_id"], item["access_key"], self.secret)

    def test_upload_signature_enforcement(self):
        with self.assertRaises(service.CaseError):
            self.create(uploads=[FakeEvidence("fake.pdf", b"not a PDF")])
        with self.assertRaises(service.CaseError):
            self.create(uploads=[FakeEvidence("script.exe", b"MZ")])

    def test_rate_limit(self):
        for _ in range(service.MAX_CASES_PER_HOUR):
            self.create()
        with self.assertRaises(service.CaseError) as caught:
            self.create()
        self.assertEqual(caught.exception.status, 429)

    def test_require_ownership_and_safe_reference(self):
        dossier = make_dossier()
        dossier["rights_declared"] = False
        with self.assertRaises(service.CaseError):
            service.create_case(dossier, [], "192.0.2.6", self.secret)
        dossier = make_dossier()
        dossier["product_url"] = "file:///etc/passwd"
        with self.assertRaises(service.CaseError):
            service.create_case(dossier, [], "192.0.2.6", self.secret)


if __name__ == "__main__":
    unittest.main()
