"""Executable isolation, privacy, reviewer-gate and status tests for AYAR."""
import io
import json
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
        "ai_processing_consent": True, "publication_consent": public,
    }


def make_review(conflict=False):
    return {
        "criteria": {
            key: {"score": 4 if not (key == "rights" and conflict) else 1,
                  "evidence": "Verified test record with versioned source reference"}
            for key, _, _ in service.RUBRICS["ebook"]
        },
        "review_mode": "ai_assisted",
        "ai_review_reference": "AYAR manual analysis session case evidence reviewed 2026-10-27",
        "evidence_fingerprint": service.staff_case(service.staff_list()[0]["case_id"])["evidence_fingerprint"],
        "evidence_examined": True,
        "independence_statement": "AYAR Expert Engine is a MojPlayWin-affiliated AI-assisted process, not an independent human reviewer.",
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
        self.assertEqual(len(record["events"]), 2)
        self.assertNotIn("contact_email", record)
        with self.assertRaises(service.CaseError):
            service.case_status(item["case_id"], "incorrect-access-key", self.secret)

    def test_specialized_product_categories_support_full_review_rubrics(self):
        categories = ["course","dataset","website","mobileapp","template","audio","video","model3d"]
        self.assertEqual(len(service.CASE_TYPES), 12)
        self.assertTrue(set(categories).issubset(service.CASE_TYPES))
        for index, category in enumerate(categories):
            dossier = make_dossier()
            dossier["category"] = category
            dossier["product_name"] = "Real category validation - " + category
            item = service.create_case(dossier, [], "192.0.2." + str(70 + index), self.secret)
            private = service.case_status(item["case_id"], item["access_key"], self.secret)
            self.assertEqual(private["category"], category)
            self.assertEqual(private["status"], "submitted")
            rubric = service.RUBRICS[category]
            self.assertEqual(len(rubric), 8)
            self.assertEqual(sum(weight for _, weight, _ in rubric), 100)
            self.assertTrue(any(critical for _, _, critical in rubric))
            criteria = {key: {"score": 4, "evidence": "Reproducible category-specific source check"} for key, _, _ in rubric}
            scored, score, blockers = service.validate_review(category, criteria)
            self.assertEqual(len(scored), 8)
            self.assertAlmostEqual(score, 80.0)
            self.assertFalse(blockers)

    def test_staff_queue_and_lifecycle(self):
        item = self.create(public=True)
        queue = service.staff_list()
        self.assertEqual(len(queue), 1)
        self.assertEqual(queue[0]['case_id'], item['case_id'])
        service.set_status(item["case_id"], "in_review", "staff:12", "Review began after triage")
        reviewed = service.submit_review(item["case_id"], "staff:12", make_review(), self.secret)
        self.assertEqual(reviewed["status"], "reviewed")
        self.assertAlmostEqual(reviewed["score"], 80.0)
        self.assertTrue(reviewed["public_report"])
        self.assertEqual(len(service.registry(self.secret)), 1)
        user = service.case_status(item["case_id"], item["access_key"], self.secret)
        self.assertEqual(user["review"]["schema"], "AYAR-AI-ASSISTED-REVIEW-v1")
        self.assertEqual(user["review"]["reviewer_alias"], "AYAR Expert Engine")
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
        service.set_status(item["case_id"], "in_review", "staff:8", "Review resumed after applicant response")
        service.submit_review(item["case_id"], "staff:8", make_review(), self.secret)
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
        service.set_status(item["case_id"], "in_review", "staff:1", "A documented review is underway")
        result = service.submit_review(item["case_id"], "staff:1", make_review(), self.secret)
        self.assertFalse(result["public_report"])
        self.assertEqual(service.registry(self.secret), [])

    def test_critical_criterion_override(self):
        item = self.create(public=True)
        service.set_status(item["case_id"], "in_review", "staff:1", "A documented review is underway")
        result = service.submit_review(item["case_id"], "staff:1", make_review(conflict=True), self.secret)
        self.assertEqual(result["grade"], "Critical gate failure")

    def test_conflicts_and_incomplete_evidence_are_blocked(self):
        item = self.create()
        service.set_status(item["case_id"], "in_review", "staff:1", "A documented review is underway")
        review = make_review()
        review["no_material_conflict"] = False
        with self.assertRaises(service.CaseError):
            service.submit_review(item["case_id"], "staff:1", review, self.secret)
        review = make_review()
        review["criteria"]["sources"]["evidence"] = "short"
        with self.assertRaises(service.CaseError):
            service.submit_review(item["case_id"], "staff:1", review, self.secret)


    def test_cannot_finalise_before_review_or_while_information_is_pending(self):
        item = self.create()
        code, key = item["case_id"], item["access_key"]
        with self.assertRaises(service.CaseError) as unstarted:
            service.submit_review(code, "staff:1", make_review(), self.secret)
        self.assertEqual(unstarted.exception.status, 409)
        service.set_status(code, "needs_information", "staff:1",
                           "Please provide the latest rights evidence")
        with self.assertRaises(service.CaseError) as pending:
            service.submit_review(code, "staff:1", make_review(), self.secret)
        self.assertEqual(pending.exception.status, 409)
        with self.assertRaises(service.CaseError) as bypass:
            service.set_status(code, "in_review", "staff:1",
                               "Bypass the missing evidence request")
        self.assertEqual(bypass.exception.status, 409)
        self.assertEqual(service.case_status(code, key, self.secret)["status"], "needs_information")
        service.append_case_evidence(
            code, key, "This is the requested full provenance clarification", [], self.secret)
        service.set_status(code, "in_review", "staff:1", "Review resumed after applicant evidence")
        self.assertEqual(service.submit_review(code, "staff:1", make_review(), self.secret)["status"], "reviewed")

    def test_decline_is_terminal_and_requires_reason(self):
        item = self.create()
        code, key = item["case_id"], item["access_key"]
        with self.assertRaises(service.CaseError):
            service.set_status(code, "declined", "staff:1", "short")
        self.assertEqual(service.case_status(code, key, self.secret)["status"], "submitted")
        service.set_status(code, "declined", "staff:1",
                           "Submission outside the accepted review scope")
        events = service.case_status(code, key, self.secret)["events"]
        with self.assertRaises(service.CaseError) as reopen:
            service.set_status(code, "in_review", "staff:1", "Reopen declined case")
        self.assertEqual(reopen.exception.status, 409)
        with self.assertRaises(service.CaseError):
            service.submit_review(code, "staff:1", make_review(), self.secret)
        self.assertEqual(service.case_status(code, key, self.secret)["events"], events)


    def test_public_report_integrity_valid_tampered_and_private(self):
        item = self.create(public=True)
        code = item["case_id"]
        service.set_status(code, "in_review", "staff:12", "Start reproducible evidence review")
        service.submit_review(code, "staff:12", make_review(), self.secret)
        record = service.case_status(code, item["access_key"], self.secret)
        proof = record["review"]["integrity"]["proof"]
        self.assertEqual(len(proof), 64)
        self.assertTrue(record["review_integrity_valid"])
        entry = service.registry(self.secret)[0]
        self.assertEqual(entry["proof"], proof)
        verified = service.verify_public_report(code, proof, self.secret)
        self.assertTrue(verified["verified"])
        self.assertEqual(verified["product_name"], "Principles of Digital Economics")
        self.assertNotIn("requester_email", verified)
        self.assertFalse(service.verify_public_report(code, "0" * 64, self.secret)["verified"])
        self.assertFalse(service.verify_public_report("AYR-26-000000000000", proof, self.secret)["verified"])
        with service.database() as db, db:
            row = db.execute("SELECT review FROM cases WHERE code=?", (code,)).fetchone()
            changed = json.loads(row["review"])
            changed["score"] = 99.9
            db.execute("UPDATE cases SET review=? WHERE code=?",
                       (json.dumps(changed), code))
        self.assertEqual(service.registry(self.secret), [])
        self.assertFalse(service.verify_public_report(code, proof, self.secret)["verified"])
        self.assertFalse(service.case_status(code, item["access_key"], self.secret)["review_integrity_valid"])

    def test_private_signed_report_is_not_publicly_disclosed(self):
        item = self.create(public=False)
        code = item["case_id"]
        service.set_status(code, "in_review", "staff:6", "Review provenance and quality")
        service.submit_review(code, "staff:6", make_review(), self.secret)
        private = service.case_status(code, item["access_key"], self.secret)
        self.assertTrue(private["review_integrity_valid"])
        proof = private["review"]["integrity"]["proof"]
        self.assertFalse(service.verify_public_report(code, proof, self.secret)["verified"])
        self.assertEqual(service.registry(self.secret), [])


    def test_explicit_ai_authorization_and_legacy_case_opt_in(self):
        invalid = make_dossier()
        invalid["ai_processing_consent"] = False
        with self.assertRaises(service.CaseError):
            service.create_case(invalid, [], "192.0.2.64", self.secret)
        item = self.create()
        code, key = item["case_id"], item["access_key"]
        with service.database() as db, db:
            db.execute("DELETE FROM events WHERE code=? AND action='ai_processing_consent'", (code,))
        self.assertFalse(service.case_status(code, key, self.secret)["ai_processing_consent"])
        service.set_status(code, "in_review", "staff:9", "Review authorization checkpoint")
        with self.assertRaises(service.CaseError) as denied:
            service.submit_review(code, "staff:9", make_review(), self.secret)
        self.assertEqual(denied.exception.status, 403)
        self.assertTrue(service.grant_ai_consent(code, key, self.secret)["ai_processing_consent"])
        self.assertEqual(service.submit_review(code, "staff:9", make_review(), self.secret)["status"], "reviewed")
        with self.assertRaises(service.CaseError):
            service.grant_ai_consent(code, key, self.secret)

    def test_ai_review_provenance_and_actual_evidence_checks(self):
        item = self.create()
        code = item["case_id"]
        service.set_status(code, "in_review", "staff:5", "Review evidence and method")
        review = make_review()
        review["ai_review_reference"] = ""
        with self.assertRaises(service.CaseError):
            service.submit_review(code, "staff:5", review, self.secret)
        review = make_review()
        review["evidence_examined"] = False
        with self.assertRaises(service.CaseError):
            service.submit_review(code, "staff:5", review, self.secret)
        review = make_review()
        review["review_mode"] = "human"
        with self.assertRaises(service.CaseError):
            service.submit_review(code, "staff:5", review, self.secret)


    def test_evidence_fingerprint_binds_review_to_exact_applicant_revision(self):
        item = self.create()
        code, key = item["case_id"], item["access_key"]
        first = service.case_status(code, key, self.secret)["evidence_fingerprint"]
        self.assertEqual(first, service.staff_case(code)["evidence_fingerprint"])
        self.assertEqual(len(first), 64)
        old_analysis = make_review()
        service.set_status(code, "needs_information", "staff:8",
                           "Provide a signed authorization file for the latest edition")
        answer = service.append_case_evidence(
            code, key, "Signed authorization attached for the revised edition",
            [FakeEvidence("rights.txt", b"Rights verification for latest edition")],
            self.secret
        )
        self.assertEqual(answer["status"], "submitted")
        second = service.staff_case(code)["evidence_fingerprint"]
        self.assertNotEqual(first, second)
        service.set_status(code, "in_review", "staff:8",
                           "Reopened with applicant's additional evidence")
        with self.assertRaises(service.CaseError) as outdated:
            service.submit_review(code, "staff:8", old_analysis, self.secret)
        self.assertEqual(outdated.exception.status, 409)
        current = make_review()
        self.assertEqual(current["evidence_fingerprint"], second)
        self.assertEqual(service.submit_review(code, "staff:8", current, self.secret)["status"], "reviewed")
        final = service.case_status(code, key, self.secret)
        self.assertEqual(final["review"]["evidence_fingerprint"], second)
        self.assertTrue(final["review_integrity_valid"])

    def test_missing_or_forged_evidence_fingerprint_rejected(self):
        item = self.create()
        code = item["case_id"]
        service.set_status(code, "in_review", "staff:6", "Review started")
        review = make_review()
        review.pop("evidence_fingerprint")
        with self.assertRaises(service.CaseError):
            service.submit_review(code, "staff:6", review, self.secret)
        review["evidence_fingerprint"] = "0" * 64
        with self.assertRaises(service.CaseError) as mismatch:
            service.submit_review(code, "staff:6", review, self.secret)
        self.assertEqual(mismatch.exception.status, 409)
        self.assertEqual(service.staff_case(code)["status"], "in_review")

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
