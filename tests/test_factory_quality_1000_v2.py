"""Fail-closed boundaries for the 100 independent factory quality groups."""
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "factory_quality_1000_v2", ROOT / "scripts" / "factory_quality_1000_v2.py"
)
quality = importlib.util.module_from_spec(spec)
spec.loader.exec_module(quality)


class FactoryQualityDomainVetoTests(unittest.TestCase):
    def test_domain_veto_matches_each_criteria_specialist_dimension(self):
        for domain, group in quality.DOMAIN_VETO.items():
            with self.subTest(domain=domain, group=group):
                self.assertIn(domain, quality.CRITERIA[group]["quality_dimensions"])

    def test_delivery_blocker_does_not_erase_conflict_disclosure_evidence(self):
        with tempfile.TemporaryDirectory() as name:
            folder = Path(name)
            evidence = {}
            for group, sentence in (
                ("Q085", b"delivery and recovery checks pending independent verification"),
                ("Q095", b"conflicts-of-interest disclosure stays separate from delivery"),
            ):
                path = folder / (group + ".txt")
                path.write_bytes(group.encode("ascii") + b": " + sentence + b"\n" * 8)
                evidence[group] = {
                    "path": path.name,
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                }

            baseline = quality.grade({"blockers": []}, criteria_evidence=evidence,
                                     evidence_root=folder)
            self.assertEqual(baseline["criteria"]["Q085"]["documentary_points"], 10)
            self.assertEqual(baseline["criteria"]["Q095"]["documentary_points"], 10)

            blocked = quality.grade(
                {"blockers": [{"code": "P0_PROOF_MISSING:distribution_support_reliability"}]},
                criteria_evidence=evidence, evidence_root=folder,
            )
            self.assertEqual(blocked["criteria"]["Q085"]["documentary_points"], 0)
            self.assertEqual(blocked["criteria"]["Q095"]["documentary_points"], 10)
            self.assertEqual(blocked["documentary_evidence_points"], 10)
            self.assertFalse(blocked["release_allowed"])
            self.assertIsNone(blocked["product_quality_points"])


if __name__ == "__main__":
    unittest.main()
