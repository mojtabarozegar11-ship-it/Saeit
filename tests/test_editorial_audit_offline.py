"""Test the read-only audit aggregator without Django or a database."""

import unittest
from types import SimpleNamespace

from core.editorial_audit import summarize_editorial_stories


class EditorialAuditTests(unittest.TestCase):
    @staticmethod
    def story(pk, title, status):
        return SimpleNamespace(pk=pk, title=title, summary="", body="", seo_keywords=[], source=None, status=status)

    def test_counts_unsafe_stories_without_mutation(self):
        entries = [
            self.story(1, "Wheat harvest", "published"),
            self.story(2, "Israeli farming", "published"),
            self.story(3, "Parliament debates agriculture", "scheduled"),
            self.story(4, "انتخابات مجلس", "draft"),
        ]
        original = [(x.pk, x.title, x.status) for x in entries]
        report = summarize_editorial_stories(entries)
        self.assertEqual(report["scanned"], 4)
        self.assertEqual(report["blocked_total"], 3)
        self.assertEqual(report["blocked_by_reason"], {"israel_related": 1, "political_news": 2})
        self.assertEqual(report["public_or_scheduled_blocked_total"], 2)
        self.assertEqual(report["public_or_scheduled_blocked_ids_sample"], [2, 3])
        self.assertEqual(report["published_missing_final_signature_total"], 2)
        self.assertEqual(report["published_missing_final_signature_ids_sample"], [1, 2])
        self.assertEqual([(x.pk, x.title, x.status) for x in entries], original)

    def test_signed_published_story_is_not_counted_as_unsigned(self):
        signed = self.story(8, "Crop report", "published")
        signed.body = "گزارش علمی\n\n#مجتبی_روزگار"
        result = summarize_editorial_stories([signed])
        self.assertEqual(result["published_missing_final_signature_total"], 0)

    def test_sample_is_capped_without_losing_total(self):
        entries = [self.story(i, "election results", "published") for i in range(40)]
        report = summarize_editorial_stories(entries, max_ids=3)
        self.assertEqual(report["public_or_scheduled_blocked_total"], 40)
        self.assertEqual(report["public_or_scheduled_blocked_ids_sample"], [0, 1, 2])


if __name__ == "__main__":
    unittest.main()
