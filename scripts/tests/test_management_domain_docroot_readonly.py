"""Fail-closed tests for redacted management domain root evidence."""
import unittest

from scripts.management_domain_docroot_readonly import sanitize


class DocrootReceiptTests(unittest.TestCase):
    def test_exact_domain_docroot_sanitized(self):
        result = sanitize({"result": {"status": 1, "data": {
            "domain": "zomorodmelal.ir",
            "documentroot": "/home/zomorod2/public_html",
            "secret": "must-not-appear",
        }}})
        self.assertTrue(result["expected_public_html_attested"])
        self.assertEqual(result["target_domain_records"], 1)
        self.assertNotIn("/home/zomorod2", str(result))
        self.assertNotIn("must-not-appear", str(result))
        self.assertFalse(result["active_python_interpreter_attested"])
        self.assertFalse(result["release_permitted"])

    def test_other_domain_not_accepted(self):
        result = sanitize({"result": {"status": 1, "data": {
            "domain": "mojplaywin.com",
            "documentroot": "/home/zomorod2/public_html",
        }}})
        self.assertFalse(result["expected_public_html_attested"])
        self.assertEqual(result["document_root_class"], "not_reported")

    def test_conflicting_paths_fail_closed(self):
        result = sanitize({"result": {"status": 1, "data": [
            {"domain": "zomorodmelal.ir", "docroot": "/home/zomorod2/public_html"},
            {"domain": "zomorodmelal.ir", "docroot": "/other"},
        ]}})
        self.assertEqual(result["document_root_class"], "ambiguous")
        self.assertFalse(result["expected_public_html_attested"])

    def test_failure_response_rejected(self):
        with self.assertRaises(ValueError):
            sanitize({"result": {"status": 0, "data": {}}})


if __name__ == "__main__":
    unittest.main()
