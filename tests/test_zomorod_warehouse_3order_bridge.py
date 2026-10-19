import importlib.util
import json
import sqlite3
import tempfile
import unittest
import zipfile
import hashlib
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def load(path,name):
 spec=importlib.util.spec_from_file_location(name,path)
 obj=importlib.util.module_from_spec(spec);spec.loader.exec_module(obj);return obj

bridge=load(ROOT/"scripts/zomorod_vps_warehouse_3order_bridge.py","site_three_bridge")
orders=load(ROOT/"scripts/factory_continuous_production_orders.py","factory_existing_order_engine")
imp=load(ROOT/"scripts/zomorod_factory_store_import.py","zomorod_store_import")

class BridgeTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory()
  self.root=Path(self.tmp.name)
  (self.root/"production-instructions"/"orders").mkdir(parents=True)
  self.families=[{"id":f"F{i:02d}","slug":f"family_{i:02d}","name_fa":f"محصول تخصصی {i}"} for i in range(1,41)]
 def tearDown(self):self.tmp.cleanup()
 def test_issue_exactly_three_and_replay_safe(self):
  first=bridge.orders_once(self.root,orders,self.families,"2026-10-19")
  self.assertEqual(first["new"],3)
  self.assertEqual(len(first["orders"]),3)
  second=bridge.orders_once(self.root,orders,self.families,"2026-10-19")
  self.assertEqual(second["new"],0)
  self.assertEqual(first["orders"],second["orders"])
  self.assertEqual(len(list((self.root/"production-instructions"/"orders").glob("WO-*.json"))),3)
  docs=[orders.validate_old(p) for p in (self.root/"production-instructions"/"orders").glob("*.json")]
  self.assertEqual({x["bridge_slot"] for x in docs},{1,2,3})
  self.assertTrue(all(x["publication_approved"] is False for x in docs))
  self.assertTrue(all(x["warehouse_goods_created"] is False for x in docs))
  self.assertEqual({x["family_id"] for x in docs}, {f["family_id"] for f in docs})
 def test_two_distinct_runs_same_day_produce_six(self):
  one=bridge.orders_once(self.root,orders,self.families,"2026-10-19-r39280060178")
  two=bridge.orders_once(self.root,orders,self.families,"2026-10-19-r39280909089")
  self.assertEqual(one["new"],3)
  self.assertEqual(two["new"],3)
  self.assertEqual(len(list((self.root/"production-instructions"/"orders").glob("WO-*.json"))),6)
  self.assertEqual(bridge.orders_once(self.root,orders,self.families,"2026-10-19-r39280909089")["new"],0)
 def test_second_real_cycle_adds_exactly_three(self):
  bridge.orders_once(self.root,orders,self.families,"2026-10-19")
  next_=bridge.orders_once(self.root,orders,self.families,"2026-10-20")
  self.assertEqual(next_["new"],3)
  self.assertEqual(len(list((self.root/"production-instructions"/"orders").glob("WO-*.json"))),6)
 def test_capacity_blocks_without_fake_orders(self):
  with self.assertRaisesRegex(RuntimeError,"CAPACITY"):
   bridge.orders_once(self.root,orders,self.families,"2026-10-19",max_active=2)
  self.assertEqual(len(list((self.root/"production-instructions"/"orders").glob("WO-*.json"))),0)
 def test_wrong_cycle_or_unverified_family(self):
  with self.assertRaises(ValueError):bridge.orders_once(self.root,orders,self.families,"../../etc")
  with self.assertRaises(ValueError):bridge.registry(self.root/"missing")
 def test_native_queue_300_full_stages_three_then_promotes_after_real_capacity(self):
  area=self.root/"production-instructions"
  queue=area/"orders"
  for number in range(1,301):
   ident=f"WO-{number:08d}"
   (queue/(ident+".json")).write_text(json.dumps({
       "schema":orders.SCHEMA,"id":ident,"status":"issued",
       "fingerprint":"0"*64,"public_distribution_allowed":False
   }))
  day="2026-10-19-r39286724057"
  manifest,created=bridge.stage_three_requests(self.root,orders,self.families,day)
  self.assertTrue(created)
  self.assertEqual(len(manifest["requests"]),3)
  self.assertEqual({q["state"] for q in manifest["requests"]},{"awaiting_native_capacity"})
  self.assertTrue(all(q["native_work_order"] is None for q in manifest["requests"]))
  again,created=bridge.stage_three_requests(self.root,orders,self.families,day)
  self.assertFalse(created)
  self.assertEqual(again["requests"],manifest["requests"])
  blocked=bridge.reconcile_site_intake(self.root,orders,self.families)
  self.assertTrue(blocked["capacity_blocked"])
  self.assertEqual(blocked["orders"],[])
  self.assertEqual(len(list(queue.glob("WO-*.json"))),300)
  # Native capacity is freed only by recorded completed work, not deletion.
  for number in range(1,4):
   p=queue/(f"WO-{number:08d}.json")
   data=json.loads(p.read_text())
   data["status"]="completed_verified"
   p.write_text(json.dumps(data))
  admitted=bridge.reconcile_site_intake(self.root,orders,self.families)
  self.assertEqual(admitted["orders"],["WO-00000301","WO-00000302","WO-00000303"])
  self.assertEqual(admitted["admitted_cycles"],1)
  self.assertEqual(len(list(queue.glob("WO-*.json"))),303)
  receipt=area/"zomorod-site-intake"/(day+".json")
  result=json.loads(receipt.read_text())
  self.assertTrue(all(q["state"]=="admitted" for q in result["requests"]))
  self.assertEqual([q["native_work_order"] for q in result["requests"]],admitted["orders"])
  replay=bridge.reconcile_site_intake(self.root,orders,self.families)
  self.assertEqual(replay["orders"],[])
  self.assertEqual(len(list(queue.glob("WO-*.json"))),303)

 def test_two_cycles_stage_six_distinct_requests_without_native_capacity(self):
  for day in ("2026-10-19","2026-10-20"):
   doc,created=bridge.stage_three_requests(self.root,orders,self.families,day)
   self.assertTrue(created)
   self.assertEqual(len(doc["requests"]),3)
  files=list((self.root/"production-instructions"/"zomorod-site-intake").glob("*.json"))
  self.assertEqual(len(files),2)
  ids=[q["request_id"] for p in files for q in json.loads(p.read_text())["requests"]]
  self.assertEqual(len(set(ids)),6)

 def test_store_import_sha_and_idempotency(self):
  inbox=self.root/"inbox";dbpath=self.root/"site_store.sqlite3"
  with sqlite3.connect(dbpath) as db:
   db.execute("CREATE TABLE products (id INTEGER)")
   db.execute("CREATE TABLE payment_state (id INTEGER)")
  recipe="farm_enterprise_economics"
  pack_dir=inbox/"packages"/recipe;pack_dir.mkdir(parents=True)
  with zipfile.ZipFile(pack_dir/"artifact.zip","w") as zipf:
   zipf.writestr(recipe+"/readme.txt", "original audited demonstration archive")
  original=pack_dir/"artifact.zip"
  digest=hashlib.sha256(original.read_bytes()).hexdigest()
  z=pack_dir/(digest+".zip");original.rename(z)
  (pack_dir/(digest+".json")).write_text(json.dumps({
   "recipe":recipe,"artifact_sha256":digest,"name":"Original agricultural calculator",
   "qa_status":"passed","commercial_status":"private_internal_qa_pass_not_published",
   "owner_publication_approval":False,"public_listing_enabled":False,"price":None}))
  receipt=inbox/"receipts"/recipe;receipt.mkdir(parents=True)
  (receipt/(digest+".json")).write_text(json.dumps({
   "recipe":recipe,"sha256":digest,"status":"received_private"}))
  first=imp.import_catalog(inbox,dbpath)
  self.assertEqual(first["imported"],1)
  self.assertEqual(imp.import_catalog(inbox,dbpath)["imported"],0)
  with sqlite3.connect(dbpath) as db:
   self.assertEqual(db.execute("SELECT public_enabled FROM factory_drafts").fetchone()[0],0)
   self.assertIsNone(db.execute("SELECT paid_price_irr FROM factory_drafts").fetchone()[0])
  data=json.loads((pack_dir/(digest+".json")).read_text())
  data["qa_status"]="failed"
  (pack_dir/(digest+".json")).write_text(json.dumps(data))
  with self.assertRaises(ValueError):imp.import_catalog(inbox,dbpath)

 def test_delivery_does_not_count_previous_receipts_as_new_goods(self):
  import types
  root=self.root
  stock=[]
  for i in range(5):
   recipe=f"product_{i}"
   directory=root/"digital-products"/recipe
   directory.mkdir(parents=True)
   version=hashlib.sha256((recipe+"-source").encode()).hexdigest()
   artifact=hashlib.sha256((recipe+"-archive").encode()).hexdigest()
   (directory/"manufacturing_manifest.json").write_text(json.dumps({
      "source_sha256":version,"artifact_sha256":artifact}))
   stock.append({"product_id":recipe,"version":version,"artifact_sha256":artifact,
      "manufacturing_qc":"passed","commercial_release":False})
  warehouse=types.SimpleNamespace(stock_summary=lambda _:stock)
  sender=types.SimpleNamespace(
    host_ssh_options=lambda *a:[],
    deliver=lambda recipe,*a,**kw:{"recipe":recipe,
       "status":"already_received" if recipe in ("product_0","product_1","product_2")
                else "received_private"})
  results=bridge.deliver_stock(root,root/"production-warehouse",warehouse,sender,
       root/"unused.key",root/"unused.known",max_products=2)
  self.assertTrue(results)
  self.assertTrue(all(r["status"]=="received_private" for r in results))
  self.assertEqual(len(results),2)

if __name__=="__main__":unittest.main()
