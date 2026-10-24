"""Contract tests: 100,000 original words per paid agricultural text project.

Generated stress-test strings are TEST FIXTURES, not agricultural manuscripts.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "scripts/agri200_doctoral_books_v1_20261024.py"
spec = importlib.util.spec_from_file_location("doctoral_books", TARGET)
books = importlib.util.module_from_spec(spec)
spec.loader.exec_module(books)


class DoctoralBooksContractTests(unittest.TestCase):
    def test_exact_catalog_split_and_100k_per_selling_edition(self):
        rows, catalog_sha = books.catalog_rows(ROOT / "docs/agri200_p0_catalog.tsv")
        self.assertEqual(len(rows), 200)
        self.assertEqual(len(catalog_sha), 64)
        plans = [books.book_plan(ident, fa, en, rank, f"WO-{rank:08d}", catalog_sha)
                 for rank, (ident, fa, en) in enumerate(rows, 1)]
        self.assertEqual(sum(p["selling_locale"] == "en-US" for p in plans), 100)
        self.assertEqual(sum(p["selling_locale"] == "fa-IR" for p in plans), 100)
        self.assertEqual(sum(p["minimum_original_prose_words"] for p in plans), 20_000_000)
        self.assertEqual(sum(len(p["chapter_work_units"]) for p in plans), 4000)
        self.assertTrue(all(not p["sales_enabled"] and
                            not p["quality1000_approved"] and
                            p["discount_percent"] == 0 for p in plans))

    def test_existing_short_scaffold_never_reaches_100k(self):
        chapters = ["## Chapter 1\n\nThe evidence is incomplete and needs review."] * 20
        result = books.original_prose_metrics(chapters)
        self.assertLess(result["substantive_prose_words"], 100_000)
        self.assertFalse(result["meets_mechanical_length_and_novelty"])
        self.assertIn("P0_ORIGINAL_PROSE_UNDER_100000_WORDS",
                      result["critical_findings"])

    def test_copy_paste_padding_is_rejected_even_if_word_floor_exceeded(self):
        long_repetition = " ".join(["soil moisture diagnosis needs real research"] * 950)
        chapters = [long_repetition] * 20
        result = books.original_prose_metrics(chapters)
        self.assertGreaterEqual(result["substantive_prose_words"], 100_000)
        self.assertIn("P0_REPETITIVE_PADDING_OR_LOW_NOVELTY",
                      result["critical_findings"])
        self.assertFalse(result["meets_mechanical_length_and_novelty"])

    def test_unique_synthetic_stress_fixture_meets_only_mechanical_threshold(self):
        chapters = []
        for chapter in range(20):
            paragraphs = []
            for paragraph in range(53):
                paragraphs.append(" ".join(
                    f"scholarlytoken{chapter}block{paragraph}item{word}"
                    for word in range(100)))
            chapters.append("\n\n".join(paragraphs))
        result = books.original_prose_metrics(chapters)
        self.assertGreaterEqual(result["substantive_prose_words"], 100_000)
        self.assertTrue(result["meets_mechanical_length_and_novelty"])
        self.assertFalse(result["independent_doctoral_science_review_verified"])
        self.assertFalse(result["qc1000_approved"])
        self.assertFalse(result["commercial_release"])

    def test_bibliography_and_tables_do_not_count_as_original_prose(self):
        body = ("## Introduction\n\nThe introductory comparison needs revision.\n"
                "## References\n\n" + "Copied bibliography entry number. " * 100_000)
        self.assertLess(len(books.prose_tokens(body)), 20)
        self.assertEqual(len(books.prose_tokens("| a | b | c |\n")), 0)

    def test_actual_two_hundred_order_plan_is_private_and_idempotent(self):
        rows, sha = books.catalog_rows(ROOT / "docs/agri200_p0_catalog.tsv")
        with tempfile.TemporaryDirectory() as d:
            private = Path(d)
            area = private / "production-instructions"
            orders = area / "orders"
            orders.mkdir(parents=True)
            order_ids = []
            for rank, (ident, fa, en) in enumerate(rows, 1):
                order_id = f"WO-{rank:08d}"
                order_ids.append(order_id)
                payload = {"id": ident, "fa": fa, "en": en}
                origin_sha = hashlib.sha256(json.dumps(
                    payload, ensure_ascii=False, sort_keys=True,
                    separators=(",", ":")).encode("utf-8")).hexdigest()
                (orders / (order_id + ".json")).write_text(
                    json.dumps({"id": order_id, "source_product_id": ident,
                                "priority_rank": rank,
                                "source_sha256": origin_sha}), encoding="utf-8")
            (area / "owner-agri200-p0-index.json").write_text(json.dumps({
                "catalog_sha256": sha, "topic_count": 200,
                "edition_goal_count": 400, "order_ids_ranked": order_ids,
            }), encoding="utf-8")
            report = books.execute(private, ROOT / "docs/agri200_p0_catalog.tsv")
            self.assertEqual(report["new_private_plans"], 200)
            self.assertEqual(report["chapter_authoring_work_units"], 4000)
            self.assertEqual(report["full_100k_word_monographs_completed"], 0)
            self.assertEqual(report["published_for_sale"], 0)
            self.assertFalse(report["sites_modified"])
            rerun = books.execute(private, ROOT / "docs/agri200_p0_catalog.tsv")
            self.assertEqual(rerun["new_private_plans"], 0)
            self.assertEqual(rerun["new_private_source_screens"], 0)


if __name__ == "__main__":
    unittest.main()
