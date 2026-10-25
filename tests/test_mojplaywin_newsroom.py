"""Regression checks: no cross-domain records, fabricated news, or unapproved release."""
import tempfile
import unittest
from pathlib import Path

from core.mojplaywin_newsroom import Newsroom, fingerprint, is_mojplaywin, quality_score


def valid_story():
    return {
        "category": "ai", "origin": "external",
        "title": "An evidence-led evaluation of AI-assisted creative production systems",
        "summary": "This overview identifies the main research assumptions, the state of available evidence, the uncertainty in reported results, the effects on creative workflows, and practical controls for responsible digital product teams.",
        "body": ("The context of this report is a real research question. "
                 "The practical impact of AI adoption requires reproducible data, critical review "
                 "and documented risks. We distinguish observations from interpretation. "
                 "The research report describes methodology, evidence limitations and "
                 "operational implications for teams building digital products. ") * 8,
        "analysis": ("Independent analysis: the data supports a limited interpretation. "
                     "Any implementation requires a reproducible benchmark, privacy controls, "
                     "source attribution and a documented quality review before deployment. ") * 5,
        "keywords": ["AI workflows", "quality assurance", "digital products"],
        "event_date": "2026-10-18", "source_url": "https://example.org/research/ai",
        "publisher": "Example independent research archive",
        "source_title": "AI systems and creative work",
        "evidence": "Traceable externally attributed research record: document hash and review notes.",
    }


class NewsroomTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Newsroom(Path(self.tmp.name) / "private" / "news.sqlite3")

    def tearDown(self):
        self.tmp.cleanup()

    def test_hostname_boundary(self):
        self.assertTrue(is_mojplaywin("mojplaywin.com"))
        self.assertTrue(is_mojplaywin("www.mojplaywin.com:443"))
        for host in ("zomorodmelal.ir", "mojplaywin.com.evil.org", "other.com"):
            self.assertFalse(is_mojplaywin(host))

    def test_full_quality_score_and_editor_approval(self):
        draft = valid_story()
        score, checks = quality_score(draft)
        self.assertEqual(score, 100)
        self.assertTrue(all(checks.values()))
        story_id, saved_score = self.store.create_draft(draft)
        self.assertEqual(saved_score, 100)
        self.assertEqual(self.store.list_published(), [])
        self.assertEqual(self.store.publish_due(), 0)
        self.assertTrue(self.store.approve(story_id, "human-site-owner"))
        self.assertEqual(self.store.publish_due(), 1)
        self.assertEqual(self.store.publish_due(), 0)
        articles = self.store.list_published()
        self.assertEqual(len(articles), 1)
        self.assertEqual(articles[0]["title"], draft["title"])
        self.assertEqual(articles[0]["approved_by"], "human-site-owner")
        self.assertEqual(self.store.get_published(articles[0]["slug"])["score"], 100)

    def test_low_quality_is_held(self):
        draft = valid_story()
        draft["summary"] = "incomplete"
        draft["body"] = "speculation"
        draft["analysis"] = "none"
        story_id, score = self.store.create_draft(draft)
        self.assertLess(score, 90)
        self.assertFalse(self.store.approve(story_id, "site-owner"))
        self.assertEqual(self.store.publish_due(), 0)
        self.assertEqual(self.store.stats()["blocked"], 1)

    def test_duplicate_is_rejected(self):
        self.store.create_draft(valid_story())
        with self.assertRaisesRegex(Exception, "UNIQUE"):
            self.store.create_draft(valid_story())
        self.assertEqual(self.store.stats()["draft"], 1)

    def test_external_source_attribution_is_mandatory(self):
        draft = valid_story()
        draft["source_url"] = "http://insecure.invalid/news"
        with self.assertRaisesRegex(ValueError, "HTTPS"):
            self.store.create_draft(draft)

    def test_schedule_must_be_timezone_aware(self):
        story_id, _ = self.store.create_draft(valid_story())
        with self.assertRaisesRegex(ValueError, "timezone"):
            self.store.approve(story_id, "owner", "2026-10-18T12:30:00")
        self.assertTrue(self.store.approve(story_id, "owner", "2099-10-18T12:30:00+00:00"))
        self.assertEqual(self.store.publish_due("2026-10-18T12:30:00+00:00"), 0)

    def test_private_storage_not_public_root(self):
        for unsafe in ("/home/example/public_html/news.sqlite3",
                       "/home/example/mojplaywin.com/news.sqlite3"):
            with self.assertRaises(ValueError):
                Newsroom(Path(unsafe))


if __name__ == "__main__":
    unittest.main()
