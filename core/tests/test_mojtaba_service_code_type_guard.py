"""Regression: malformed JSON service_code must fail closed without a TypeError."""
import unittest

from core.mojtaba_commercial_services import InvalidService, generate


class ServiceCodeTypeGuardTests(unittest.TestCase):
    def test_non_string_codes_rejected_as_domain_errors(self):
        for code in (None, False, 1, [], {}, ["AGR-01"]):
            with self.subTest(code=code):
                with self.assertRaises(InvalidService):
                    generate({"service_code": code, "data": {}}, "digest")

    def test_unknown_string_rejected(self):
        with self.assertRaises(InvalidService):
            generate({"service_code": "UNKNOWN", "data": {}}, "digest")

    def test_seo_priority_non_string_fails_closed(self):
        valid = {"id": "SEO-1", "category": "indexing", "state": "unknown",
                 "priority": "high", "evidence_ref": ""}
        for priority in (None, False, 1, [], {}, ["high"]):
            with self.subTest(priority=priority):
                check = dict(valid, priority=priority)
                with self.assertRaises(InvalidService):
                    generate({"service_code": "SEO-01", "data": {"checks": [check]}}, "digest")
