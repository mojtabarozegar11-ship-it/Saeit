"""Synthetic contract tests for additive active-PHP release patching."""
import tempfile
from pathlib import Path
import unittest

from scripts.zm_business_live_report_patch import ANCHORS, patch


class LivePHPAdditivePatchTests(unittest.TestCase):
    def source(self):
        return "<?php\n"+("/* synthetic operational code */\n"*400)+"\n".join(
            old for old, _ in ANCHORS
        )+"\n"

    def test_all_existing_logic_preserved_except_three_bounded_insertions(self):
        source = self.source()
        result = patch(source)
        self.assertIn("zmBusinessChatgptReports($private);", result)
        self.assertIn("authorize('users');", result)
        self.assertIn("'chatgpt_reports'=>'گزارش‌های متنی ChatGPT'", result)
        self.assertIn("/* synthetic operational code */", result)
        self.assertEqual(result.count("/* synthetic operational code */"), 400)
        for old, new in ANCHORS:
            self.assertEqual(result.count(new), 1)
        self.assertTrue(result.startswith("<?php"))

    def test_missing_or_duplicate_anchor_fails_closed(self):
        source = self.source()
        with self.assertRaisesRegex(ValueError, "MISSING_OR_DUPLICATE"):
            patch(source.replace(ANCHORS[0][0], ""))
        with self.assertRaisesRegex(ValueError, "MISSING_OR_DUPLICATE"):
            patch(source + ANCHORS[1][0])

    def test_no_double_application_or_partial_update(self):
        patched = patch(self.source())
        with self.assertRaisesRegex(ValueError, "ALREADY_PRESENT"):
            patch(patched)

    def test_reject_unexpected_size(self):
        with self.assertRaisesRegex(ValueError, "SIZE_UNEXPECTED"):
            patch("<?php")


if __name__ == "__main__":
    unittest.main()
