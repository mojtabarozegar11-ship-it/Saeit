"""Regression coverage for original offline wheat tool + separate free/paid catalog."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "content/zomorod-v11/free-products/wheat-seed-rate-planner-v1/index.html"
LIB = ROOT / "content/zomorod-v11/site_store.php"
INDEX = ROOT / "content/zomorod-v11/store_index.php"

class FreeWheatProduct(unittest.TestCase):
    def test_page_is_self_contained_and_free(self):
        data = PAGE.read_text(encoding="utf-8")
        self.assertIn('window.ZomorodSeedRate={seedRate}', data)
        self.assertIn('download="wheat-seed-rate-planner-v1.html"', data)
        self.assertIn("کاملاً آفلاین", data)
        self.assertIn("قوه نامیه", data)
        self.assertIn("وزن هزار دانه", data)
        self.assertNotRegex(data, r'(?i)<script[^>]+src=')
        self.assertNotRegex(data, r'(?i)fetch\s*\(|XMLHttpRequest|localStorage')
        self.assertTrue(4500 <= len(data.encode("utf-8")) <= 30000)

    @unittest.skipUnless(shutil.which("node"), "Node.js required")
    def test_scientific_calculation_and_bad_inputs(self):
        body = PAGE.read_text(encoding="utf-8")
        script = re.search(r"<script>(.*?)</script>", body, re.S)
        self.assertIsNotNone(script)
        js = script.group(1)
        runner = """
const fs=require('fs'),vm=require('vm');
const js=fs.readFileSync(process.argv[2],'utf8');
const values={density:350,tkw:40,germ:95,emergence:85,area:1};
const nodes={result:{set textContent(v){},append(){}},calculate:{addEventListener(name,fn){this.click=fn;}}};
for(const [id,value] of Object.entries(values)){nodes[id]={value:String(value)};}
const doc={getElementById(id){return nodes[id]},createElement(){return {innerHTML:'',querySelector(){return {set textContent(v){}}}}}};
const ctx={window:{},document:doc,Number,Error};
// CI virtual machines can be briefly CPU-constrained; keep a finite timeout.
vm.runInNewContext(js,ctx,{timeout:5000});
const calc=ctx.window.ZomorodSeedRate.seedRate;
const r=calc(350,40,95,85,1);
const expected=350/(.95*.85)*40/100;
if(Math.abs(r.kgHa-expected)>1e-10||Math.abs(r.totalKg-expected)>1e-10)throw Error('wrong wheat seed rate');
if(Math.abs(calc(350,40,100,100,2).totalKg-280)>1e-10)throw Error('wrong 100% case');
for(const args of [[350,40,0,90,1],[350,40,99,0,1],[NaN,40,95,85,1],[350,40,95,85,-1]]){
  let threw=false;try{calc(...args)}catch(e){threw=true}if(!threw)throw Error('unsafe input admitted')
}
console.log("OFFLINE_WHEAT_TOOL_FUNCTIONAL_QA=PASS");
"""
        with tempfile.TemporaryDirectory() as d:
            a=Path(d)/"product.js";b=Path(d)/"test.js"
            a.write_text(js);b.write_text(runner)
            run=subprocess.run(["node",str(b),str(a)],capture_output=True,text=True,timeout=15)
        self.assertEqual(run.returncode,0,run.stderr)
        self.assertIn("FUNCTIONAL_QA=PASS",run.stdout)

    @unittest.skipUnless(shutil.which("php"), "PHP required")
    def test_paid_catalog_stays_positive_and_free_catalog_stays_zero(self):
        code = r"""
<?php
require $argv[1];
$db=zmStoreDb($argv[2]);
$paid=$db->query("SELECT sql FROM sqlite_master WHERE name='products'")->fetchColumn();
$free=$db->query("SELECT sql FROM sqlite_master WHERE name='free_digital_products'")->fetchColumn();
if(strpos($paid,'CHECK(price_irr>0)')===false || strpos($free,'CHECK(price_irr=0)')===false)exit(20);
try {$db->exec("INSERT INTO products(sku,title,description,price_irr) VALUES('zero','bad','bad',0)");exit(21);}catch(PDOException $e){}
$db->prepare("INSERT INTO free_digital_products(sku,title,description,download_path,artifact_sha256,license_text,price_irr,enabled) VALUES(?,?,?,?,?,?,0,1)")->execute(['wheat_seed_rate_v1','Wheat seed','Offline verified tool','/store/free-products/wheat-seed-rate-planner-v1/index.html',str_repeat('a',64),'Free educational use']);
if($db->query("SELECT COUNT(*) FROM free_digital_products WHERE enabled=1")->fetchColumn()!=1)exit(22);
echo "FREE_SEPARATE_FROM_PAID=PASS";
"""
        with tempfile.TemporaryDirectory() as d:
            script=Path(d)/"test.php";script.write_text(code)
            run=subprocess.run(["php",str(script),str(LIB),d],capture_output=True,text=True,timeout=10)
        self.assertEqual(run.returncode,0,run.stderr+run.stdout)
        self.assertIn("FREE_SEPARATE_FROM_PAID=PASS",run.stdout)

    def test_native_public_catalog_enforces_local_download_and_no_payment(self):
        body = INDEX.read_text(encoding="utf-8")
        self.assertIn("free_digital_products WHERE enabled=1",body)
        self.assertIn("رایگان — بدون پرداخت",body)
        self.assertIn("download rel=",body)
        self.assertIn("preg_match('#^/store/free-products/",body)
        self.assertIn("foreach($items as $p)",body)
        self.assertNotIn("payment_intent",body.lower())

if __name__=="__main__":
    unittest.main()
