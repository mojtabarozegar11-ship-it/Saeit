"""Regression tests for the private ZM receipt validator; no network or database."""
import unittest
from scripts.validate_zm_actions_receipt import validate

HEADER = "## گزارش ۰۵-۰۰۵۷ | 2026-11-03 13:05 UTC | ZM-CTRL-20261103-0057"
URL = "https://github.com/mojtabarozegar11-ship-it/Saeit/pull/1837"

def receipt(actions, code="05-0057", header=HEADER):
    import json
    return header + "\nZM_ACTIONS_V1_START\n" + json.dumps(
        {"version": 1, "report_code": code, "actions": actions}, ensure_ascii=False
    ) + "\nZM_ACTIONS_V1_END"

def action(identifier="ZM05-0057-A01", status="completed", url=URL):
    return {"id": identifier, "title_fa": "کنترل رسید", "status": status,
            "evidence_url": url, "impact_fa": "کاهش خطای ورود"}

class ReceiptTests(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(validate(receipt([action()])), [])

    def test_non_object_payload(self):
        self.assertIn("receipt must be a JSON object",
                      validate(HEADER + "\nZM_ACTIONS_V1_START\n[]\nZM_ACTIONS_V1_END"))

    def test_wrong_report_code(self):
        self.assertIn("report code does not match header",
                      validate(receipt([action()], code="05-0058")))

    def test_duplicate_action_id(self):
        self.assertTrue(any("duplicate id" in e for e in validate(receipt([action(), action()]))))

    def test_completed_without_evidence(self):
        self.assertTrue(any("completed without evidence" in e for e in validate(receipt([action(url="")]))))

    def test_partial_with_evidence(self):
        self.assertTrue(any("incomplete action" in e for e in validate(receipt([action(status="partial")]))))

    def test_invalid_evidence_domain(self):
        self.assertTrue(any("invalid evidence URL" in e for e in validate(receipt([action(url="https://evil.example/pull/1")]))))

    def test_too_many_actions(self):
        self.assertTrue(any("at most 20" in e for e in validate(receipt([action() for _ in range(21)]))))

    def test_malformed_json(self):
        self.assertIn("invalid JSON receipt", validate(HEADER + "\nZM_ACTIONS_V1_START\n{\nZM_ACTIONS_V1_END"))

if __name__ == "__main__":
    unittest.main()
