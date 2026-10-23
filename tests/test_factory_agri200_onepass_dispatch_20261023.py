"""Release safety and deterministic dispatch tests for the 200 P0 orders."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


SOURCE = Path(__file__).resolve().parents[1] / "scripts/factory_agri200_onepass_dispatch_20261023.py"
spec = importlib.util.spec_from_file_location("agri200_onepass", SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class OnePassTests(unittest.TestCase):
    def test_exact_200_orders_and_audit_never_promotes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "private"
            area = root / "production-instructions"
            ops = Path(directory) / "operations/production-instructions"
            area.mkdir(parents=True)
            ops.mkdir(parents=True)
            orders = ["WO-%08d" % i for i in range(1, 201)]
            (area / "owner-agri200-p0-index.json").write_text(json.dumps({
                "topic_count": 200, "edition_goal_count": 400,
                "order_ids_ranked": orders}), encoding="utf8")
            result = module.dispatch(root, ops, run_workers=False)
            self.assertEqual(result["before"]["stage2_researched"], 0)
            self.assertEqual(result["after"]["internal_orders"], 200)
            self.assertEqual(result["after"]["planned_language_editions"], 400)
            self.assertFalse(result["after"]["storefront_release_verified"])
            self.assertFalse(result["public_sites_modified"])
            self.assertEqual(result["finished_products_published_by_this_dispatch"], 0)

    def test_duplicate_internal_orders_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            area = root / "production-instructions"
            area.mkdir()
            (area / "owner-agri200-p0-index.json").write_text(json.dumps({
                "topic_count": 200, "edition_goal_count": 400,
                "order_ids_ranked": ["WO-00000001"] * 200}))
            with self.assertRaisesRegex(RuntimeError, "INDEX_INTEGRITY_FAILED"):
                module.indexed_orders(root)

    def test_stage_order_has_no_fake_approval_or_store_step(self):
        labels = [stage[0] for stage in module.STAGES]
        self.assertEqual(labels, [
            "outside_literature_scout", "scientific_research",
            "bilingual_design_and_prototype", "private_workbook_draft",
            "technical_preflight_and_rework", "source_specific_revision_brief"])
        self.assertTrue(all("publish" not in label and "approve" not in label
                            for label in labels))


if __name__ == "__main__":
    unittest.main()
