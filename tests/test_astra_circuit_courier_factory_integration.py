"""Separate nonrecursive factory packaging proof for the fourth game family."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT=Path(__file__).resolve().parents[1]
P=ROOT/"product_prototypes"/"circuit_courier"


class CircuitCourierFactoryIntegrationTests(unittest.TestCase):
    def test_factory_registration_packs_original_game_without_sale(self):
        spec=importlib.util.spec_from_file_location(
            "astra_circuit_private_pipeline",ROOT/"scripts"/"astra_v2_private_pipeline.py")
        mod=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.assertIn("circuit_courier_v1",mod.BUILDERS)
        with tempfile.TemporaryDirectory() as temp:
            root=mod.safe_root(Path(temp)/"private")
            brief={
                "brief_id":"indie_puzzle_game_reference_v1",
                "builder":"circuit_courier_v1",
                "development_scope":"private_reference_prototype",
                "publication_allowed":False,
                "market_demand_verified":False,
                "paid_api_budget":0,
                "problem":"Develop an original offline grid puzzle and validate all 36 deterministic solvable levels with an independent BFS check.",
            }
            self.assertTrue(mod.enqueue(root,brief)["new_job"])
            result=mod.tick(root)
            self.assertEqual(result["status"],"PRIVATE_QA_PASSED",result)
            self.assertEqual(result["new_products_for_sale"],0)
            qa=json.loads(next(root.glob("qa-*.json")).read_text())
            for key in ("commercial_product","sale_ready","qualified_market_opportunity",
                        "independent_domain_review","real_payment_allowed",
                        "public_deployment_allowed"):
                self.assertFalse(qa[key])
            self.assertIsNone(qa["quality_score"])
            archives=list(root.glob("artifact-*.zip"))
            self.assertEqual(len(archives),1)
            with zipfile.ZipFile(archives[0]) as zipped:
                self.assertIsNone(zipped.testzip())
                self.assertIn("circuit_courier/index.html",zipped.namelist())
                self.assertIn("circuit_courier/engine.js",zipped.namelist())
                self.assertIn("circuit_courier/test_engine.js",zipped.namelist())
                with tempfile.TemporaryDirectory() as isolated:
                    zipped.extractall(isolated)
                    completed=subprocess.run(
                        [sys.executable,str(Path(isolated)/"circuit_courier"/"self_test.py")],
                        cwd=Path(isolated)/"circuit_courier",capture_output=True,text=True,timeout=30)
                    self.assertEqual(completed.returncode,0,completed.stderr)

    

if __name__=="__main__":
    unittest.main()
