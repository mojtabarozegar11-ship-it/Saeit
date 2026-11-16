"""Nine deterministic no-write controls for Moj Prop single-form hotfix plan."""
import hashlib
import unittest
from scripts.mojprop_surgical_horizon_patch_plan_c126 import plan

H = lambda b: hashlib.sha256(b).hexdigest()
OLD = (b'<html><form id="request-form">'
       b'<select id="horizon">'
       b'<option value="now">Today / urgent</option>'
       b'<option value="7-days">This week</option>'
       b'<option value="30-days">This month</option>'
       b'<option value="initial">Initial review only</option>'
       b'</select><input id="consent" type="checkbox"></form></html>')


class ExactByteHorizonPatchPlan(unittest.TestCase):
    def test_01_exact_static_candidate_changes_four_values(self):
        new, info = plan(OLD, H(OLD))
        self.assertTrue(info["candidate_generated"])
        self.assertEqual(info["replacement_count"], 4)
        self.assertEqual(info["original_sha256"], H(OLD))
        self.assertEqual(info["proposed_sha256"], H(new))
        self.assertIn(b'value="urgent"', new)
        self.assertIn(b'value="week"', new)
        self.assertIn(b'value="month"', new)
        self.assertIn(b'value="review"', new)
        self.assertFalse(info["production_write_authorized"])

    def test_02_unknown_live_hash_no_change(self):
        candidate, info = plan(OLD, "0" * 64)
        self.assertIsNone(candidate)
        self.assertFalse(info["candidate_generated"])

    def test_03_owner_label_edit_fails_closed(self):
        bad = OLD.replace(b"Today / urgent", b"Custom customer option")
        candidate, info = plan(bad, H(bad))
        self.assertIsNone(candidate)

    def test_04_duplicate_horizon_select_fails_closed(self):
        bad = OLD + b'<select id="horizon"></select>'
        candidate, info = plan(bad, H(bad))
        self.assertIsNone(candidate)

    def test_05_already_canonical_not_changed(self):
        new, _ = plan(OLD, H(OLD))
        again, info = plan(new, H(new))
        self.assertIsNone(again)
        self.assertFalse(info["candidate_generated"])

    def test_06_preserves_every_byte_except_exact_four_attributes(self):
        data = OLD + b"<!-- private@example.invalid?csrf=NEVER_LOG -->"
        new, info = plan(data, H(data))
        self.assertTrue(info["only_horizon_value_attributes_modified"])
        self.assertIn(b"private@example.invalid?csrf=NEVER_LOG", new)
        self.assertNotIn("private", str(info))
        self.assertNotIn("NEVER_LOG", str(info))

    def test_07_disallow_unbounded_html(self):
        data = OLD + b"x" * 513000
        candidate, info = plan(data, H(data))
        self.assertIsNone(candidate)

    def test_08_extra_option_refused(self):
        data = OLD.replace(b'</select>', b'<option value="other">Other</option></select>')
        candidate, info = plan(data, H(data))
        self.assertIsNone(candidate)

    def test_09_never_attest_backup_or_server_or_payment(self):
        candidate, info = plan(OLD, H(OLD))
        self.assertFalse(info["independent_file_backup_verified"])
        self.assertFalse(info["post_apply_http_verified"])
        self.assertFalse(info["production_write_authorized"])
        self.assertFalse(info["backend_database_or_payment_modified"])


if __name__ == "__main__":
    unittest.main()
