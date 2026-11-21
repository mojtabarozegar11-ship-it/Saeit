"""Commercial enquiry fallback for the existing Zomorod store; no new checkout."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
STORE=ROOT/"content/zomorod-v11/store_index.php"
LIB=ROOT/"content/zomorod-v11/site_store.php"
class StoreContactContracts(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.src=STORE.read_text("utf8")
  cls.paid=cls.src.split("foreach($items as $p){",1)[1].split("echo '<section id=",1)[0]
 def test_store_only_lists_enabled_products(self):
  self.assertIn("products WHERE enabled=1",self.src)
 def test_official_phone_fallback_for_paid_items(self):
  self.assertIn('href="tel:+989022048691"',self.paid)
 def test_existing_form_still_available(self):
  self.assertIn('href="/ask-master/index.php?service=1"',self.paid)
 def test_no_false_payment_promise(self):
  self.assertIn("ثبت درخواست به معنای خرید یا پرداخت نیست",self.paid)
 def test_sku_remains_visible_and_escaped(self):
  self.assertIn("storeEsc($p['sku'])",self.paid)
 def test_price_still_irr(self):
  self.assertIn("number_format((int)$p['price_irr'])",self.paid)
 def test_general_service_fallback_when_products_empty(self):
  self.assertIn("تماس برای استعلام کالا و خدمات",self.src)
 def test_official_contact_link_retained(self):
  self.assertIn('href="/contact/"',self.src)
 def test_gateway_stays_off(self):
  self.assertIn("در این وضعیت خرید آنلاین و برداشت وجه غیرفعال است",self.src)
 def test_no_payment_or_order_submission_added(self):
  for unsafe in ("payment_intent","<form method=","INSERT INTO orders","fetch("):
   self.assertNotIn(unsafe,self.paid)
 def test_no_change_to_free_items(self):
  self.assertIn("رایگان — بدون پرداخت",self.src)
  self.assertIn("free_digital_products WHERE enabled=1",self.src)
 def test_existing_mobile_wrap_retained(self):
  self.assertIn("overflow-wrap:anywhere",self.src)
 @unittest.skipUnless(shutil.which("php"),"php required")
 def test_php_syntax(self):
  r=subprocess.run(["php","-l",str(STORE)],capture_output=True,text=True,timeout=12)
  self.assertEqual(r.returncode,0,r.stdout+r.stderr)

@unittest.skipUnless(shutil.which("php"),"php required")
class RenderedContactFunnel(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  r=subprocess.run(["php","-r","exit(extension_loaded('pdo_sqlite')?0:1);"],capture_output=True)
  if r.returncode:raise unittest.SkipTest("pdo_sqlite required")
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  root=Path(self.tmp.name)
  self.private=root/".private/zomorod-business";self.private.mkdir(parents=True)
  self.index=root/"public_html/store/index.php";self.index.parent.mkdir(parents=True)
  shutil.copyfile(LIB,self.private/"site_store.php")
  shutil.copyfile(STORE,self.index)
 def render(self,sql=""):
  code="require $argv[1];$db=zmStoreDb($argv[2]);"+sql
  seed=subprocess.run(["php","-r",code,str(self.private/"site_store.php"),str(self.private)],capture_output=True,text=True,timeout=15)
  self.assertEqual(seed.returncode,0,seed.stderr)
  p=subprocess.run(["php",str(self.index)],capture_output=True,text=True,timeout=15)
  self.assertEqual(p.returncode,0,p.stderr)
  return p.stdout
 def test_empty_catalog_still_has_public_phone(self):
  p=self.render()
  self.assertIn("کاتالوگ در حال تکمیل",p)
  self.assertIn("تماس برای استعلام کالا و خدمات",p)
 def test_enabled_item_offers_form_and_phone_not_hidden(self):
  seed='$db->exec("INSERT INTO products(sku,title,description,price_irr,enabled) VALUES (\\x27PAID01\\x27,\\x27محصول آزمایشی\\x27,\\x27توضیحات\\x27,450000,1),(\\x27OFF01\\x27,\\x27غیرفعال\\x27,\\x27توضیحات\\x27,200000,0)");'
  p=self.render(seed)
  self.assertIn("PAID01",p)
  self.assertNotIn("OFF01",p)
  self.assertIn("450,000 ریال",p)
  self.assertIn("تماس مستقیم برای استعلام",p)
  self.assertIn("درخواست بررسی خرید و پیش‌فاکتور",p)
 def test_title_is_escaped(self):
  seed="""$stmt=$db->prepare("INSERT INTO products(sku,title,description,price_irr,enabled) VALUES(?,?,?,?,1)");$stmt->execute(['SAFEX01','<script>alert(1)</script>','توضیح تست',120000]);"""
  p=self.render(seed)
  self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;",p)
  self.assertNotIn("<script>alert(1)</script>",p)
if __name__=="__main__":unittest.main()
