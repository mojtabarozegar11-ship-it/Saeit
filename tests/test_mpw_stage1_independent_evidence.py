"""Independent 43-return dossier tests; never fake expert signatures."""
import io,json,tempfile,unittest,zipfile
from pathlib import Path
from scripts import mpw_vps_warehouse_courier as courier
from scripts import mpw_stage1_independent_evidence as evidence
from scripts import factory_native_customer_packager as native

class ReviewDossierTests(unittest.TestCase):
 def setUp(self):
  tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
  self.root=Path(tmp.name)
  self.product="sample_native"
  self.version="a"*64
  b=io.BytesIO()
  with zipfile.ZipFile(b,"w",zipfile.ZIP_DEFLATED) as z:
   z.writestr("assets/readme.md","This is original synthetic sample content.")
   z.writestr("assets/icon.svg",'<svg xmlns="http://www.w3.org/2000/svg"><circle cx="5" cy="5" r="4"/></svg>')
  self.raw=b.getvalue()
  stock=self.root/"production-warehouse/finished"/self.product/self.version
  stock.mkdir(parents=True)
  self.manifest={"schema":"saeit.factory.production-warehouse.v1","product_id":self.product,
    "source_sha256":self.version,"artifact_sha256":courier.digest(self.raw),
    "bytes":len(self.raw),"manufacturing_qc":"passed","production_state":"finished_goods_in_factory",
    "commercial_release":False,"site_transfer_state":"not_transferred",
    "content_rights_market_review":"pending","receiving_site":None,
    "family_id":"F34"}
  (stock/"product.zip").write_bytes(self.raw)
  (stock/"warehouse_manifest.json").write_text(json.dumps(self.manifest))
  req={"schema":courier.RETURN_SCHEMA,"tenant":courier.TENANT,"product_id":self.product,
    "source_sha256":self.version,"artifact_sha256":courier.digest(self.raw),
    "stage":1,"status":"return_for_qa_completion","issues":list(courier.ISSUES),
    "published":False,"factory_original_must_be_preserved":True}
  dir=self.root/"design-intake/mojplaywin-stage1-quality-returns"
  dir.mkdir(parents=True)
  self.path=dir/(self.product+"-"+self.version+".json")
  self.path.write_text(json.dumps(req))
 def test_complete_three_review_roles_never_claimed_signed(self):
  native.pack(self.root,self.product,self.version,self.manifest,self.raw,courier)
  result=evidence.run(self.root)
  self.assertEqual(result["validated_stage1_returns"],1)
  self.assertEqual(result["native_structure_only"],1)
  doc=evidence.read(self.root/"design-state/mojplaywin-independent-evidence/open"/self.path.name)
  self.assertEqual(len(doc["human_qa_open_issues"]),3)
  self.assertTrue(all(x["real_evidence_received"] is False for x in doc["human_qa_open_issues"]))
  self.assertFalse(doc["customer_sale_and_site_publication_permitted"])
  second=evidence.run(self.root)
  self.assertEqual(second["existing_unaltered_dossiers_verified"],1)
 def test_tampering_stock_causes_fail_closed(self):
  stock=self.root/"production-warehouse/finished"/self.product/self.version
  (stock/"product.zip").write_bytes(b"changed original")
  with self.assertRaises((RuntimeError,ValueError)):
   evidence.run(self.root)
 def test_private_no_customer_preview_reports_missing(self):
  result=evidence.run(self.root)
  self.assertEqual(result["missing_technical_companions"],1)
  self.assertEqual(result["products_commercially_authorized"],0)
if __name__=="__main__":unittest.main()
