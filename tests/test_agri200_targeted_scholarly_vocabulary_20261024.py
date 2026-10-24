"""Targeted scholarly vocabulary must not weaken the Stage2 evidence gate."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "targeted_scholarly_scout", ROOT / "scripts/factory_stage2_literature_scout.py")
S = importlib.util.module_from_spec(spec)
spec.loader.exec_module(S)


class TargetedScholarlyVocabularyTests(unittest.TestCase):
    def test_all_sixteen_gap_topics_have_search_queries_and_normalized_aliases(self):
        self.assertEqual(len(S.TARGETED_SCHOLAR_VOCAB), 16)
        self.assertEqual(set(S.TARGETED_SCHOLAR_VOCAB), set(S.TARGETED_SCHOLAR_SEARCHES))
        for title, aliases in S.TARGETED_SCHOLAR_VOCAB.items():
            variants = S.query_variants(title.title())
            self.assertGreaterEqual(len(variants), 3)
            special = S.TARGETED_SCHOLAR_SEARCHES[title]
            self.assertEqual(variants[:len(special)], list(special))
            self.assertEqual(len(set(variants)), len(variants))
            terms = S.keys(title.title())
            self.assertGreaterEqual(len(terms), 3, title)
            self.assertTrue(all(S.normalize(alias) in terms for alias in aliases[:2]),
                            title)
            self.assertLessEqual(len(terms), 7)
            self.assertTrue(all("http" not in q and ":" not in q
                                for q in variants), title)

    def test_unresolved_agri200_gaps_have_topic_specific_scholar_queries(self):
        gardening = S.query_variants("Gardening Equipment Checklist")
        self.assertEqual(gardening[:4], list(S.TARGETED_SCHOLAR_SEARCHES[
            "gardening equipment checklist"]))
        self.assertIn(S.normalize("agricultural"), S.keys("Gardening Equipment Checklist"))
        troubleshooting = S.query_variants("Farming Troubleshooting FAQ")
        self.assertEqual(troubleshooting[:4], list(S.TARGETED_SCHOLAR_SEARCHES[
            "farming troubleshooting faq"]))
        self.assertIn(S.normalize("disease"), S.keys("Farming Troubleshooting FAQ"))
        self.assertIn(S.normalize("decision"), S.keys("Farming Troubleshooting FAQ"))

    def test_only_exact_title_gets_special_searches(self):
        self.assertFalse(any("cucurbita" in q for q in
                             S.query_variants("Houseplant Rescue Guide")))
        self.assertNotIn("honeybee", S.keys("Carrot and Radish Growing"))
        self.assertEqual(S.evidence_gap_reason({}, []),
                         "under_four_topic_relevant_article_abstracts")

    def test_same_domain_studies_remain_rejected(self):
        papers = [{
            "host": "journal.example.edu", "publisher": "One Scientific Publisher",
            "support_sentence": f"Relevant distinct evidence number {i}.",
            "relevance_score": 8, "publication_year": 2021,
            "openalex_id": f"https://openalex.org/W{900000000+i}",
        } for i in range(5)]
        self.assertEqual(S.diverse_four_or_five(papers), [])
        self.assertEqual(S.evidence_gap_reason({}, papers),
                         "insufficient_independent_publishers_or_domains")

    def test_existing_v10_packets_can_still_be_accepted_only_after_revalidation(self):
        self.assertTrue(S.SCOUT_ALGO_VERSION.startswith("v12-"))
        self.assertNotEqual(S.SCOUT_ALGO_VERSION,
                            "v10-complete-page-grid-source-diversity")


if __name__ == "__main__":
    unittest.main()
