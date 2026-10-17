"""Exact 100/100, no rounding and no missing Lighthouse scores."""
import unittest

from scripts.mojplaywin_lighthouse_gate import CATEGORIES, DEVICES, PAGES, check_report


class MojPlayWinLighthouseStrictGateTests(unittest.TestCase):
    def report(self, scores):
        return {"categories": {k: {"score": v} for k, v in scores.items()}}

    def test_exact_all_four_100_is_accepted(self):
        result = check_report(self.report({key: 1.0 for key in CATEGORIES}))
        self.assertTrue(result["passes_100_out_of_100"])
        self.assertEqual(result["failed"], {})

    def test_ninety_nine_is_rejected(self):
        for category in CATEGORIES:
            with self.subTest(category=category):
                scores = {key: 1.0 for key in CATEGORIES}
                scores[category] = .99
                verdict = check_report(self.report(scores))
                self.assertFalse(verdict["passes_100_out_of_100"])
                self.assertIn(category, verdict["failed"])

    def test_missing_and_null_scores_are_rejected(self):
        for score in (None, 0.999, 0, .5):
            with self.subTest(score=score):
                scores = {key: 1.0 for key in CATEGORIES}
                scores["seo"] = score
                result = check_report(self.report(scores))
                self.assertFalse(result["passes_100_out_of_100"])
        self.assertFalse(check_report(self.report({}))["passes_100_out_of_100"])

    def test_every_offline_main_site_preview_is_a_required_lighthouse_target(self):
        import ast
        from pathlib import Path
        source = Path(__file__).resolve().parents[1] / "scripts" / "mojplaywin_atelier_visual_preview.py"
        tree = ast.parse(source.read_text(encoding="utf-8"))
        assignments = [node for node in tree.body if isinstance(node, ast.Assign)
                       and any(isinstance(t, ast.Name) and t.id == "ROUTES" for t in node.targets)]
        self.assertEqual(len(assignments), 1)
        routes = ast.literal_eval(assignments[0].value)
        self.assertEqual(set(PAGES), set(routes))
        self.assertGreaterEqual(len(PAGES), 22)
        for page in routes.values():
            self.assertTrue(page.startswith("/"))
            self.assertNotIn("mojtaba.roozegar", page)
            self.assertNotIn("/picm/", page)
            self.assertNotIn("/farnaz/", page)

    def test_both_mobile_and_desktop_with_real_main_site_pages(self):
        self.assertEqual(set(DEVICES), {"mobile", "desktop"})
        self.assertIn("home", PAGES)
        self.assertIn("store", PAGES)
        self.assertIn("research", PAGES)
        self.assertEqual(len(set(PAGES)), len(PAGES))


if __name__ == "__main__":
    unittest.main()
