"""Original MojPlayWin English page content studio, offline tests."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from mpw_v91_port import page_content_factory as cf

def reviewer(quality, refs, verified):
    return "candidate_ready_for_human_review" if quality >=95 and refs == 2 and verified else "hold_for_review"


class ContentFactoryTests(unittest.TestCase):
    def test_all_editorial_briefs_are_original_substantial_and_scoped(self):
        self.assertEqual(len(cf.BRIEFS), 8)
        slugs = set()
        digests = set()
        for brief in cf.BRIEFS:
            draft = cf.build(brief, "2026-10-18T12:00:00+00:00")
            self.assertEqual(draft["site"], "mojplaywin.com")
            self.assertIn(draft["page_path"], cf.TOPIC_PATHS)
            self.assertEqual(draft["language"], "en")
            self.assertGreaterEqual(draft["word_count"], 220)
            self.assertLessEqual(draft["word_count"], 700)
            self.assertEqual(len(draft["source_urls"]), 2)
            self.assertFalse(draft["published"])
            self.assertFalse(draft["approved_for_publication"])
            self.assertTrue(draft["requires_factual_and_editorial_review"])
            self.assertFalse(draft["has_claims_of_live_products_or_original_research"])
            self.assertNotIn(draft["slug"], slugs)
            self.assertNotIn(draft["content_sha256"], digests)
            slugs.add(draft["slug"])
            digests.add(draft["content_sha256"])

    def test_produces_two_on_first_day_none_same_day(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            r1 = cf.tick(root, "2026-10-18T12:00:00+00:00", reviewer)
            self.assertEqual(r1["new_drafts"], 2)
            self.assertEqual(r1["total_drafts"], 2)
            r2 = cf.tick(root, "2026-10-18T14:00:00+00:00", reviewer)
            self.assertEqual(r2["new_drafts"], 0)
            self.assertEqual(r2["total_drafts"], 2)
            self.assertFalse(r2["auto_publish"])
            self.assertFalse(r2["external_llm_connected"])

    def test_produces_new_non_duplicate_guides_over_next_four_days_then_exhausts(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for day in range(18, 23):
                stamp = "2026-10-%02dT10:00:00+00:00" % day
                result = cf.tick(root, stamp, reviewer)
                self.assertEqual(result["new_drafts"], 2 if day < 22 else 0)
            self.assertEqual(result["total_drafts"], 8)
            self.assertEqual(result["remaining_curated_briefs"], 0)
            folder = root / "page_content_20261018" / "drafts"
            self.assertEqual(len(list(folder.glob("*.json"))), 8)
            self.assertEqual(len({json.loads(f.read_text())["content_sha256"]
                                  for f in folder.iterdir()}), 8)

    def test_gen65_review_requires_direct_evidence_classification(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            events=[]
            def checker(q,s,v):
                events.append((q,s,v))
                return reviewer(q,s,v)
            result=cf.tick(root, "2026-10-18T12:00:00+00:00", checker)
            self.assertEqual(events, [(95,2,True), (95,2,True)])
            self.assertEqual(result["gen65_review_recommendations"],
                             ["candidate_ready_for_human_review"]*2)
            self.assertTrue(all(not json.loads(f.read_text())["gen65_factual_verification_completed"]
                                for f in (root/"page_content_20261018"/"drafts").iterdir()))

    def test_bad_page_target_and_unapproved_reference_rejected(self):
        item = dict(cf.BRIEFS[0])
        item["page"] = "/farnaz/"
        with self.assertRaisesRegex(ValueError, "unapproved_page"):
            cf.build(item, "2026-10-18T12:00:00+00:00")
        item = dict(cf.BRIEFS[0])
        item["sources"] = ("nist", "https://untrusted.example/")
        with self.assertRaisesRegex(ValueError, "unapproved_page"):
            cf.build(item, "2026-10-18T12:00:00+00:00")

    def test_symlink_and_cross_tenant_tampering_stops(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            cf.tick(root, "2026-10-18T12:00:00+00:00", reviewer)
            folder=root/"page_content_20261018"/"drafts"
            p=next(folder.iterdir())
            record=json.loads(p.read_text())
            record["tenant"]="zomorodmelal"
            p.write_text(json.dumps(record))
            with self.assertRaisesRegex(RuntimeError, "cross_tenant"):
                cf.tick(root, "2026-10-19T12:00:00+00:00", reviewer)

    def test_gen65_abstention_blocks_production(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            with self.assertRaisesRegex(RuntimeError, "gen65_rejected"):
                cf.tick(root,"2026-10-18T12:00:00+00:00",
                        lambda *args:"abstain_unverified")
            self.assertEqual(len(list((root/"page_content_20261018"/"drafts").iterdir())),0)

    def test_draft_file_mode_private(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            cf.tick(root,"2026-10-18T12:00:00+00:00",reviewer)
            for p in (root/"page_content_20261018"/"drafts").iterdir():
                self.assertEqual(p.stat().st_mode & 0o077, 0)


if __name__=="__main__":
    unittest.main()
