import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AutonomousEvidenceAgentTests(unittest.TestCase):
    def test_agent_creates_100_source_linked_preliminary_workpapers(self):
        agent = load(ROOT / "scripts/factory_ai_evidence_analyst_agent_v1.py", "ai_evidence_agent_test")
        supplier = load(ROOT / "scripts/factory_quality_evidence_supplier_v1.py", "quality_supplier_test")
        recipe = "sample_product"
        source_sha = "a" * 64
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            version = root / "production-warehouse/finished" / recipe / source_sha
            version.mkdir(parents=True)
            archive = version / "product.zip"
            with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as out:
                out.writestr("sample_product/tests/test_sample.py",
                             "def test_ok():\n    assert True\n")
                out.writestr("sample_product/tests/test_broken.py", "def invalid(:\n")
                out.writestr("sample_product/README.md", "# Product\nEvidence gap.")
                out.writestr("sample_product/LICENSE.txt", "License text requiring legal verification.")
            artifact_sha = hashlib.sha256(archive.read_bytes()).hexdigest()
            manifest = {
                "schema": "saeit.factory.production-warehouse.v1",
                "product_id": recipe, "source_sha256": source_sha,
                "artifact_sha256": artifact_sha, "manufacturing_qc": "passed",
                "commercial_release": False, "site_transfer_state": "not_transferred",
                "bytes": archive.stat().st_size,
            }
            (version / "warehouse_manifest.json").write_text(json.dumps(manifest), encoding="utf8")
            catalog_path = root / "catalog.json"
            groups = {"Q%03d" % i: {"name": "Criterion %03d" % i,
                                    "maximum_points": 10, "quality_dimensions": []}
                      for i in range(1, 101)}
            catalog_path.write_text(json.dumps({
                "schema": "saeit.factory.quality-100-groups.v2", "group_count": 100,
                "points_per_group": 10, "total_points": 1000, "groups": groups,
            }), encoding="utf8")
            policy = supplier.catalog(catalog_path)
            dossier = agent.build_dossier(root, policy, recipe, source_sha, artifact_sha, supplier)
            self.assertEqual(len(dossier["ai_workpapers"]), 100)
            self.assertTrue(dossier["ai_evidence_is_not_human_or_independent_certification"])
            self.assertTrue(dossier["owner_directed_agent_work_product"])
            self.assertEqual(dossier["owner_delegation"]["authorization_basis"],
                             "owner_explicitly_authorized_in_chat")
            self.assertEqual(dossier["owner_delegation"]["attribution"],
                             "owner-directed agent work product; technical author remains the AI agent")
            self.assertFalse(dossier["owner_delegation"]["digital_signature_created"])
            self.assertFalse(dossier["owner_delegation"]["owner_signature_or_private_key_used"])
            self.assertFalse(dossier["owner_delegation"]["human_expert_or_licensed_counsel_replaced"])
            self.assertFalse(dossier["owner_delegation"]["legal_certification_created"])
            self.assertEqual(dossier["receipt_integrity"],
                             "SHA256_CONTENT_INTEGRITY_ONLY_NOT_DIGITAL_SIGNATURE")
            self.assertIsNone(dossier["professional_quality_1000_points"])
            rights = dossier["ai_workpapers"]["Q071"]
            self.assertEqual(rights["workpaper_state"], "AI_PRELIMINARY_ONLY")
            self.assertTrue(any(x["path"].endswith("/LICENSE.txt") for x in rights["observations"][0]["candidate_members"]))
            engineering = dossier["ai_workpapers"]["Q021"]
            test_member = next(x for x in engineering["observations"][0]["candidate_members"]
                               if x["path"].endswith("test_sample.py"))
            self.assertEqual(test_member["static_parse"], "python_ast_valid")
            self.assertEqual(test_member["test_function_count"], 1)
            plan = dossier["remediation_plan"]
            self.assertEqual(plan["distinct_criteria_routed"], 100)
            self.assertEqual(plan["static_parse_failures"], 1)
            self.assertEqual(plan["campaigns"][0]["campaign_id"], "parse-repair")
            self.assertEqual(plan["campaigns"][0]["priority"], "P0")
            self.assertEqual(plan["campaigns"][0]["source_findings_total"], 1)
            self.assertTrue(any(row["campaign_id"] == "role-engineering_test_supplier"
                                for row in plan["campaigns"]))
            self.assertEqual(plan["independent_qc_decisions_added"], 0)
            self.assertFalse(plan["commercial_release_allowed"])
            self.assertTrue(all(not row["automated_completion_means_independent_qc"]
                                for row in plan["campaigns"]))


if __name__ == "__main__":
    unittest.main()
