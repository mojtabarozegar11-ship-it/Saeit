"""Systemic factory repair: every item gets source-specific jobs, no five-item pilot."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SRC = Path(__file__).resolve().parents[1] / "scripts/factory_systemwide_science_rework_20261024.py"
spec = importlib.util.spec_from_file_location("factory_source_repair", SRC)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class ScienceRepairTests(unittest.TestCase):
    def add_item(self, area, num):
        name = "WO-%08d--r001.json" % num
        order = "WO-%08d" % num
        doi = "https://doi.org/10.1234/evidence-%d" % num
        research = {"order_id": order, "revision": 1,
                    "source_product_id": "agri-%d" % num,
                    "sources": [{"id":"scholar%d"%n,"title":"Scientific farming source "+str(n),
                      "publisher":"Indexed scholarly publisher "+str(n),"url":
                      "https://example.org/source/"+str(n),"doi":doi,
                      "source_medium":"OpenAlex bibliographic abstract; original source not independently verified"}
                     for n in range(4)],
                    "claims":[{"id":"claim%d"%n,"statement":
                                "Verbatim indexed-abstract claim requiring real full-text check "+str(n),
                                "source_ids":["scholar%d"%(n%4)]} for n in range(5)]}
        man = {"source_revision":1,"artifact_revision":3,"order_file":name,
               "order_id":order, "zip_sha256":"a"*64,"source_ids":
               [x["id"] for x in research["sources"]],
               "claim_ids":[x["id"] for x in research["claims"]],
               "public_distribution_allowed":False,"quality1000_approved":False}
        qc = {"revision":3,"mechanical_integrity_pass":True,"artifact_sha256":"a"*64,
              "independent_quality1000_approved":False}
        review = {"artifact_sha256":"a"*64, "scientific_review_state":
                  "PENDING_INDEPENDENT_VERIFIED_EVIDENCE","quality1000_approved":False}
        for sub, doc in [("stage-02/completed-dossiers", research),
                         ("stage-05/source-grounded-v003-manifests",man),
                         ("stage-06/source-grounded-v003-qc",qc),
                         ("stage-06/scientific-review-inbox-v003",review)]:
            p = area / sub
            p.mkdir(parents=True,exist_ok=True)
            (p/name).write_text(json.dumps(doc))
        return name

    def test_all_184_dynamic_and_future_order_without_original_mutation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            area = root / "production-instructions"
            for num in range(1,185):
                self.add_item(area,num)
            original = (area / "stage-02/completed-dossiers/WO-00000001--r001.json").read_bytes()
            pre = m.execute(root,dry_run=True)
            self.assertEqual(pre["checked"],184)
            self.assertEqual(pre["source_tasks"],736)
            self.assertFalse((area/"stage-02/primary-fulltext-repair-inbox").exists())
            first = m.execute(root)
            self.assertEqual(first["new_requests"],184)
            self.assertEqual(first["blocked"],0)
            self.assertEqual(m.execute(root)["existing_requests_reverified"],184)
            self.assertEqual(original,(area / "stage-02/completed-dossiers/WO-00000001--r001.json").read_bytes())
            one = json.loads((area / "stage-02/primary-fulltext-repair-inbox/WO-00000001--r001.json").read_text())
            self.assertFalse(one["all_claims_verified"])
            self.assertFalse(one["qc1000_approved"])
            self.assertEqual(len(one["scientific_claims"]),5)
            self.assertEqual(len(one["scientific_primary_source_tasks"]),4)
            self.add_item(area,185)
            future = m.execute(root)
            self.assertEqual(future["dynamic_v003_cohort"],185)
            self.assertEqual(future["new_requests"],1)

    def test_any_false_qc_or_forged_release_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            area = root / "production-instructions"
            name = self.add_item(area,1)
            p = area/"stage-06/source-grounded-v003-qc"/name
            qc = json.loads(p.read_text())
            qc["mechanical_integrity_pass"] = False
            p.write_text(json.dumps(qc))
            with self.assertRaisesRegex(m.Blocked,"FAIL_CLOSED_QC"):
                m.execute(root,dry_run=True)
            self.assertFalse((area/"stage-02/primary-fulltext-repair-inbox").exists())

    def test_existing_source_repair_ticket_is_immutable(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            area = root/"production-instructions"
            name = self.add_item(area,1)
            m.execute(root)
            p = area/"stage-02/primary-fulltext-repair-inbox"/name
            data = json.loads(p.read_text())
            data["qc1000_approved"] = True
            p.write_text(json.dumps(data))
            with self.assertRaisesRegex(m.Blocked,"SOURCE_REPAIR_HAS_BLOCKED_ORDERS"):
                m.execute(root)
            self.assertTrue(json.loads(p.read_text())["qc1000_approved"])

if __name__ == "__main__":
    unittest.main()
