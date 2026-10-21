"""Release guard: legacy free asset not certified; new 100-group asset cannot bypass."""
import hashlib,importlib.util,json
from pathlib import Path
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/"scripts/factory_commercial_quality_release_guard_v1.py"
spec=importlib.util.spec_from_file_location("factory_release_guard_1000",SRC)
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
class PublicReleaseSafety(unittest.TestCase):
    def test_new_factory_build_cannot_be_published_without_real_four_party_evidence(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            package=root/"example.zip";package.write_bytes(b"real_new_factory_package")
            sha=hashlib.sha256(package.read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError,"SIGNED_1000_QUALITY_GATE_EVIDENCE_MISSING"):
                mod.require_quality_clearance(root,"test_product",sha,
                    {"professional_quality_standard":"100_groups_x_10"},package)
    def test_old_free_release_is_not_false_labeled_1000(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            package=root/"legacy.zip";package.write_bytes(b"old free published product")
            digest=hashlib.sha256(package.read_bytes()).hexdigest()
            r=mod.require_quality_clearance(root,"farm_enterprise_economics",digest,
                                             {"qa_status":"passed"},package)
            self.assertEqual(r["status"],"LEGACY_UNASSESSED_REQUIRES_MIGRATION")
            self.assertFalse(r["1000_quality_verified"])
    def test_new_factory_cannot_smuggle_relative_path_to_quality_files(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            file=root/"factory.zip";file.write_bytes(b"data")
            with self.assertRaises(ValueError):
                mod.require_quality_clearance(root,"../../private","0"*64,
                    {"professional_quality_standard":"100_groups_x_10"},file)
if __name__=="__main__":unittest.main()
