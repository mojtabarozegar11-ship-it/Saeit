"""Owner demand: real 500-item factory-compatible intake, no fake goods."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from factory_owner_500_demand_intake import merge, validate

CATALOG = ROOT/"factory_config"/"owner_demand_500_factory_snapshot_20261022.json"
MASTER = ROOT/"factory_config"/"owner_demand_500_20261022.json"

class Owner500IntakeTest(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        self.incoming=self.root/"production-order-inputs"

    def test_500_identified_unique_products_cover_forty_families(self):
        data=json.loads(MASTER.read_text(encoding="utf8"))
        source=json.loads(CATALOG.read_text(encoding="utf8"))
        self.assertEqual(data["count"],500)
        self.assertEqual(len(data["products"]),500)
        self.assertEqual(len(validate(source,500)),500)
        self.assertEqual(len({p["id"] for p in data["products"]}),500)
        self.assertEqual(len({p["title"].casefold().strip() for p in data["products"]}),500)
        self.assertEqual({p["family_id"] for p in data["products"]},
                         {"F%02d"%i for i in range(1,41)})
        self.assertEqual([p["title"] for p in data["products"]],
                         [p["title"] for p in source["items"]])
        self.assertTrue(all(p["product_created"] is False
                            and p["quality1000_certified"] is False
                            and p["publication_approved"] is False for p in data["products"]))
        self.assertTrue(all(p["demand_evidence_verified"] is False for p in data["products"]))

    def test_import_and_second_run_are_exactly_once(self):
        first=merge(self.root,CATALOG)
        self.assertEqual(first["newly_added_to_factory_snapshot"],500)
        self.assertEqual(first["current_snapshot_items"],500)
        self.assertEqual(first["technical_products_built"],0)
        self.assertEqual(first["public_site_changes"],0)
        again=merge(self.root,CATALOG)
        self.assertEqual(again["newly_added_to_factory_snapshot"],0)
        self.assertEqual(again["already_present_exact_matches"],500)
        self.assertEqual(first["factory_snapshot_sha256"],again["factory_snapshot_sha256"])
        self.assertEqual(len(list((self.incoming/"owner-demand-history").glob("owner-proposals-*"))),1)
        self.assertEqual((self.incoming/"factory-invention-snapshot.json").stat().st_mode & 0o777,0o600)

    def test_existing_product_intake_kept_in_priority_position(self):
        self.incoming.mkdir()
        prior={"schema":"saeit.factory.production-instructions.v1",
               "custom_non_sensitive_field":"preserve",
               "items":[{"id":"existing_before_owner_500",
                         "title":"Existing owner approved prototype brief",
                         "specification":"Keep existing meaningful design goals and source provenance unchanged."}]}
        (self.incoming/"factory-invention-snapshot.json").write_text(json.dumps(prior))
        result=merge(self.root,CATALOG)
        self.assertEqual(result["previous_snapshot_items"],1)
        self.assertEqual(result["current_snapshot_items"],501)
        updated=json.loads((self.incoming/"factory-invention-snapshot.json").read_text())
        self.assertEqual(updated["items"][0],prior["items"][0])
        self.assertEqual(updated["custom_non_sensitive_field"],"preserve")
        backups=list((self.incoming/"owner-demand-history").glob("prior-*"))
        self.assertEqual(len(backups),1)
        self.assertEqual(json.loads(backups[0].read_text()),prior)

    def test_capacity_failure_preserves_prior_snapshot_unchanged(self):
        self.incoming.mkdir()
        old={"schema":"saeit.factory.production-instructions.v1",
             "items":[{"id":"older_%04d"%i,"title":"Prior owner task number %d"%i,
                       "specification":"Existing product must remain untouched, including metadata."}
                      for i in range(510)]}
        path=self.incoming/"factory-invention-snapshot.json"
        content=json.dumps(old)
        path.write_text(content)
        with self.assertRaisesRegex(ValueError,"CAPACITY_1000"):
            merge(self.root,CATALOG)
        self.assertEqual(path.read_text(),content)

    def test_existing_collision_fails_without_mutation(self):
        self.incoming.mkdir()
        source=json.loads(CATALOG.read_text())
        one=dict(source["items"][0],title="Conflicting owner demand entry title")
        p=self.incoming/"factory-invention-snapshot.json"
        original=json.dumps({"schema":source["schema"],"items":[one]})
        p.write_text(original)
        with self.assertRaisesRegex(ValueError,"ID_CONFLICT"):
            merge(self.root,CATALOG)
        self.assertEqual(p.read_text(),original)

    def test_symlink_source_rejected(self):
        alias=self.root/"catalog_alias.json"
        alias.symlink_to(CATALOG)
        with self.assertRaisesRegex(ValueError,"UNSAFE_OR_OVERSIZED"):
            merge(self.root,alias)
        self.assertFalse(self.incoming.exists())

    def test_real_order_generator_can_read_merged_500(self):
        from factory_continuous_production_orders import generate
        merge(self.root,CATALOG)
        status=generate(self.root)
        self.assertEqual(status["action"],"issued")
        self.assertEqual(status["candidate"],500)
        orders=list((self.root/"production-instructions"/"orders").glob("WO-*.json"))
        self.assertEqual(len(orders),1)
        ticket=json.loads(orders[0].read_text())
        self.assertEqual(ticket["origin"],"factory-invention-snapshot")
        self.assertFalse(ticket["public_distribution_allowed"])
        self.assertFalse(ticket["warehouse_goods_created"])
        self.assertFalse(ticket["manufacturing_qa_passed"])

if __name__=="__main__":
    unittest.main()
