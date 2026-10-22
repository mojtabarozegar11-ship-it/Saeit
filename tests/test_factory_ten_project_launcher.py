"""Ten genuine P0 launches: idempotence, stage evidence, safety boundaries."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

BASE = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, BASE / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# Standalone launcher uses its normal sibling stage libraries.
import sys
sys.path.insert(0, str(BASE / "scripts"))
import factory_agri200_p0_intake as agri
import factory_stage1_handoff as stage1
import factory_stage2_research as stage2
import factory_ten_project_launcher as launcher

CATALOG = BASE / "docs/agri200_p0_catalog.tsv"
SEED = json.loads((BASE / "docs/agri_p0_stage2_curated_research_sources_20261022.json").read_text())


class TenProjectLauncherTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.area = self.root / "production-instructions"
        topics = agri.catalog(CATALOG)[:10]
        ids = []
        for rank, (topic, fa, en) in enumerate(topics, 1):
            ident = "WO-%08d" % rank
            order = dict(agri.make_order(topic, fa, en, rank), id=ident)
            stage1.save(self.area / "orders" / (ident + ".json"), order)
            ids.append(ident)
        stage1.save(self.area / "owner-agri200-p0-index.json", {
            "schema": launcher.INDEX_SCHEMA, "topic_count": 200,
            "order_ids_ranked": ids + ["WO-%08d" % n for n in range(11, 201)],
        })

    def add_source(self, number):
        ident = "WO-%08d" % number
        order = stage1.read(self.area / "orders" / (ident + ".json"))
        evidence = copy.deepcopy(SEED["bundles"][number-1])
        evidence["work_order_sha256"] = stage2.sha(order)
        stage2.atomic(self.area / "stage-02" / "source-evidence" /
                      (order["source_product_id"] + "--r001.json"), evidence)

    def test_ten_activated_and_idempotent_no_site_changes(self):
        self.add_source(1)
        initial = launcher.run(self.root, activate=True)
        self.assertEqual(initial["projects_kicked_off"], 10)
        self.assertEqual(initial["bilingual_editions_planned"], 20)
        self.assertEqual(initial["design_started_with_sources"], 1)
        self.assertEqual(initial["research_started_needs_sources"], 9)
        before = (self.area / "ten-projects/AGRI-001/kickoff.json").read_bytes()
        self.assertEqual(launcher.run(self.root, activate=True), initial)
        self.assertEqual((self.area / "ten-projects/AGRI-001/kickoff.json").read_bytes(), before)
        for n in range(1, 11):
            directory = self.area / "ten-projects" / ("AGRI-%03d" % n)
            self.assertTrue((directory / "manufacturing-plan.json").is_file())
            self.assertFalse(stage1.read(directory / "status.json")["public_distribution_allowed"])
        self.assertFalse((self.root / "public").exists())

    def test_monitor_advances_only_when_real_source_proof_exists(self):
        launcher.run(self.root, activate=True)
        self.assertEqual(launcher.run(self.root)["research_started_needs_sources"], 10)
        self.add_source(2)
        stage2.stage2_loop(self.root, batch=20)
        changed = launcher.run(self.root)
        self.assertEqual(changed["design_started_with_sources"], 1)
        self.assertEqual(changed["research_started_needs_sources"], 9)
        self.assertEqual(len(list((self.area / "ten-projects/AGRI-002").glob(
            "stage3-design-*.json"))), 1)

    def test_monitor_will_not_forge_activation(self):
        with self.assertRaises(RuntimeError):
            launcher.run(self.root, activate=False)
        self.assertFalse((self.area / "ten-projects/AGRI-001/kickoff.json").exists())


if __name__ == "__main__":
    unittest.main()
