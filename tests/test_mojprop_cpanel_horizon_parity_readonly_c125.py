"""C125 source-only privacy and safe cPanel static candidate tests."""
import hashlib
import unittest

from scripts.mojprop_cpanel_horizon_parity_readonly_c125 import classify

SHA = lambda x: hashlib.sha256(x).hexdigest()
VALID = b'<select id="horizon"><option value="immediate">Today / urgent</option><option value="seven_days">This week</option><option value="thirty_days">This month</option><option value="explore">Initial review only</option></select>'


class OwnerStaticHorizonTests(unittest.TestCase):
    def test_01_known_old_values_are_only_candidate_when_hash_matches(self):
        x = classify(VALID, SHA(VALID))
        self.assertTrue(x["surgical_value_only_candidate"])
        self.assertTrue(x["public_http_matches_disk"])
        self.assertFalse(x["production_change_authorized"])

    def test_02_wrong_http_body_never_surgical_candidate(self):
        x = classify(VALID, "0" * 64)
        self.assertFalse(x["public_http_matches_disk"])
        self.assertFalse(x["surgical_value_only_candidate"])

    def test_03_no_unknown_labels_modified(self):
        x = classify(VALID.replace(b"Today / urgent", b"Contact the owner"), SHA(VALID))
        self.assertFalse(x["option_labels_exact_reviewed"])
        self.assertFalse(x["surgical_value_only_candidate"])

    def test_04_canonical_options_not_a_change_candidate(self):
        h = (VALID.replace(b"immediate", b"urgent")
                  .replace(b"seven_days", b"week")
                  .replace(b"thirty_days", b"month")
                  .replace(b"explore", b"review"))
        x = classify(h, SHA(h))
        self.assertTrue(x["horizon_values_canonical"])
        self.assertFalse(x["surgical_value_only_candidate"])

    def test_05_data_not_exposed_in_result(self):
        data = VALID + b"<!-- buyer@example.com csrf=SECRET -->"
        result = classify(data, SHA(data))
        import json
        raw = json.dumps(result)
        self.assertNotIn("buyer", raw)
        self.assertNotIn("SECRET", raw)
        self.assertNotIn("immediate", raw)

    def test_06_unbounded_and_missing_inputs_fail_closed(self):
        for value in (b"", b"x" * 512001, None):
            x = classify(value, SHA(VALID))
            self.assertFalse(x["surgical_value_only_candidate"])

    def test_07_malformed_option_code_is_not_rewriteable(self):
        bad = VALID.replace(b"immediate", b"../../../etc/passwd")
        x = classify(bad, SHA(bad))
        self.assertFalse(x["surgical_value_only_candidate"])

    def test_09_safe_legacy_values_can_be_labels_or_digit_hyphen_codes(self):
        variants = [
            (b"immediate", b"Today / urgent"),
            (b"seven_days", b"This week"),
            (b"thirty_days", b"This month"),
            (b"explore", b"Initial review only"),
        ]
        legacy = VALID
        for original, replacement in variants:
            legacy = legacy.replace(b'value="' + original + b'"',
                                    b'value="' + replacement + b'"')
        data = classify(legacy, SHA(legacy))
        self.assertTrue(data["option_values_safe_ascii_bounded"])
        self.assertTrue(data["option_values_distinct"])
        self.assertTrue(data["surgical_value_only_candidate"])

    def test_08_true_if_all_acceptance_and_no_customer_writes(self):
        x = classify(VALID, SHA(VALID))
        self.assertFalse(x["writes_or_customer_records_accessed"])
        self.assertFalse(x["independent_backup_verified"])
        self.assertFalse(x["production_change_authorized"])


if __name__ == "__main__":
    unittest.main()
