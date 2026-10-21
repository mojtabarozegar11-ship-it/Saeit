import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

MOD=Path(__file__).resolve().parents[1]/"scripts/factory_source_lineage_gap_audit_20261021.py"
spec=importlib.util.spec_from_file_location("source_lineage_audit",MOD)
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)

class SourceLineageGapTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup)
        self.root=Path(t.name)/"private";self.root.mkdir()
        self.orders=self.root/"quality-excellence/production-workorders"
        self.orders.mkdir(parents=True)
        self.generated=self.root/"generated-product-recipes";self.generated.mkdir()
        self.native=self.root/"native-recipes";self.native.mkdir()
    def order(self,recipe):
        folder=self.orders/recipe;folder.mkdir()
        (folder/"current.json").write_text(json.dumps({
            "schema":"saeit.factory.production-rework-order.v1",
            "recipe":recipe,
            "source_quality_receipt_sha256":"a"*64,
            "unresolved_technical_or_domain_defects":["P0_BUILD_HASH_MISMATCH"],
            "missing_documentary_group_count":95}))
    def maker(self,parent,recipe):
        folder=parent/recipe;folder.mkdir()
        (folder/"README.md").write_text("# Tested Recipe")
        (folder/"test_customer.py").write_text("assert True")
        return folder
    def test_read_only_sources_and_missing_gaps(self):
        self.order("synth_stable");self.order("missing_old")
        self.maker(self.native,"synth_stable")
        before=(self.orders/"synth_stable/current.json").read_bytes()
        doc=mod.analyze(self.root,[self.generated,self.native])
        self.assertEqual(doc["observed_workorders"],2)
        self.assertEqual(doc["source_state_counts"]["ready_for_source_revision"],1)
        self.assertEqual(doc["source_state_counts"]["missing_buildable_source"],1)
        self.assertTrue(doc["manufacturing_data_modified"] is False)
        self.assertEqual(before,(self.orders/"synth_stable/current.json").read_bytes())
    def test_ambiguous_multi_source_not_selected(self):
        self.order("same_name");self.maker(self.generated,"same_name");self.maker(self.native,"same_name")
        doc=mod.analyze(self.root,[self.generated,self.native])
        self.assertEqual(doc["source_state_counts"]["ambiguous_multiple_buildable_sources"],1)
    def test_missing_tests_not_misclassified_buildable(self):
        self.order("legacy_package")
        f=self.native/"legacy_package";f.mkdir();(f/"README.md").write_text("# Recipe")
        doc=mod.analyze(self.root,[self.generated,self.native])
        self.assertEqual(doc["source_state_counts"]["missing_buildable_source"],1)
        self.assertEqual(doc["unresolved"][0]["source_states"][1],"missing_recipe_tests")
    def test_symlink_and_duplicate_source_root_fail(self):
        self.order("single_product")
        alias=self.root/"alias";alias.symlink_to(self.native,target_is_directory=True)
        with self.assertRaisesRegex(ValueError,"SYMLINK"):
            mod.analyze(self.root,[alias])
        with self.assertRaisesRegex(ValueError,"DUPLICATED_SOURCE_ROOT"):
            mod.analyze(self.root,[self.native,self.native])

if __name__=="__main__":
    unittest.main()
