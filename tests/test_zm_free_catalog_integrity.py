"""Offline contract: the public ZM catalog never advertises altered free releases."""
import hashlib
import socket
import time
import urllib.error
import urllib.request
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "content/zomorod-v11/store_index.php"
LIB = ROOT / "content/zomorod-v11/site_store.php"
URL = "/store/free-products/wheat-seed-rate-planner-v1/index.html"


@unittest.skipUnless(shutil.which("php"), "PHP CLI required")
class FreeCatalogIntegrity(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name)
        self.store = self.home / "public_html/store"
        self.store.mkdir(parents=True)
        self.private = self.home / ".private/zomorod-business"
        self.private.mkdir(parents=True)
        shutil.copyfile(INDEX, self.store / "index.php")
        shutil.copyfile(LIB, self.private / "site_store.php")
        self.product_dir = self.store / "free-products/wheat-seed-rate-planner-v1"
        self.product_dir.mkdir(parents=True)
        self.file = self.product_dir / "index.html"
        self.file.write_bytes(b"verified original free release")
        self.sha = hashlib.sha256(self.file.read_bytes()).hexdigest()
        self.dbpath = self.private / "site_store.sqlite3"
        with sqlite3.connect(self.dbpath) as db:
            db.execute("""CREATE TABLE products (
                id INTEGER PRIMARY KEY, sku TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL, description TEXT NOT NULL,
                price_irr INTEGER NOT NULL CHECK(price_irr>0),
                enabled INTEGER NOT NULL DEFAULT 0 CHECK(enabled IN(0,1)),
                created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
            db.execute("""CREATE TABLE free_digital_products (
                id INTEGER PRIMARY KEY, sku TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL, description TEXT NOT NULL,
                download_path TEXT NOT NULL UNIQUE,
                artifact_sha256 TEXT NOT NULL, license_text TEXT NOT NULL,
                price_irr INTEGER NOT NULL DEFAULT 0 CHECK(price_irr=0),
                enabled INTEGER NOT NULL DEFAULT 0 CHECK(enabled IN(0,1)),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
            db.execute("""INSERT INTO free_digital_products
                (sku,title,description,download_path,artifact_sha256,license_text,price_irr,enabled)
                VALUES(?,?,?,?,?,?,0,1)""",
                ("wheat_seed_rate_v1", "Verified free seed calculator",
                 "Offline free artifact", URL, self.sha, "Free educational use"))

    def tearDown(self):
        self.temp.cleanup()

    def render(self):
        run = subprocess.run(["php", str(self.store / "index.php")],
                             capture_output=True, text=True, timeout=15)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertNotIn("Warning:", run.stderr)
        return run.stdout

    def update(self, column, value):
        self.assertIn(column, ("artifact_sha256", "license_text", "enabled"))
        with sqlite3.connect(self.dbpath) as db:
            db.execute(f"UPDATE free_digital_products SET {column}=?", (value,))

    def test_public_request_does_not_bootstrap_missing_database(self):
        self.dbpath.unlink()
        html = self.render()
        self.assertIn("Store temporarily unavailable", html)
        self.assertFalse(self.dbpath.exists())

    def test_public_request_does_not_repair_missing_schema(self):
        with sqlite3.connect(self.dbpath) as db:
            db.execute("DROP TABLE products")
        html = self.render()
        self.assertIn("Store temporarily unavailable", html)
        with sqlite3.connect(self.dbpath) as db:
            self.assertIsNone(db.execute(
                "SELECT name FROM sqlite_master WHERE name='products'").fetchone())

    def test_public_connection_rejects_write_even_with_existing_database(self):
        code = """<?php
require $argv[1];
$db=zmStorePublicDb($argv[2]);
// Even if query_only is disabled by a future refactor, the SQLite
// connection itself must never have permission to mutate the catalogue.
$db->exec("PRAGMA query_only=OFF");
try {$db->exec("CREATE TABLE unauthorized_public_write(x INTEGER)"); exit(19);}
catch(PDOException $e) {echo "PUBLIC_READ_ONLY=PASS";}
"""
        script = self.home / "read_only.php"
        script.write_text(code, encoding="utf8")
        run = subprocess.run(["php", str(script), str(self.private / "site_store.php"),
                              str(self.private)], capture_output=True, text=True, timeout=15)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn("PUBLIC_READ_ONLY=PASS", run.stdout)
        with sqlite3.connect(self.dbpath) as db:
            self.assertIsNone(db.execute(
                "SELECT name FROM sqlite_master WHERE name='unauthorized_public_write'").fetchone())

    def test_valid_release_is_listed_as_free_without_checkout(self):
        html = self.render()
        self.assertIn('href="' + URL + '"', html)
        self.assertIn("رایگان — بدون پرداخت", html)
        self.assertIn("خرید آنلاین و برداشت وجه غیرفعال است", html)
        self.assertNotIn("<form", html.lower())

    def test_public_catalogue_rejects_post_before_loading_private_module(self):
        # A write-like verb must never be accepted as a storefront view.
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        server = subprocess.Popen(
            ["php", "-S", f"127.0.0.1:{port}", "-t", str(self.home / "public_html")],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            for _ in range(40):
                try:
                    req = urllib.request.Request(
                        f"http://127.0.0.1:{port}/store/index.php",
                        data=b"action=product_create", method="POST")
                    urllib.request.urlopen(req, timeout=2)
                except urllib.error.HTTPError as exc:
                    self.assertEqual(exc.code, 405)
                    self.assertEqual(exc.headers.get("Allow"), "GET, HEAD")
                    self.assertNotIn("Verified free seed calculator",
                                     exc.read().decode("utf-8"))
                    break
                except urllib.error.URLError:
                    time.sleep(0.1)
            else:
                self.fail("Public store did not reject POST with HTTP 405")
        finally:
            server.terminate()
            server.wait(timeout=5)

    def test_conflicting_paid_sku_cannot_appear_as_free_release(self):
        # A legacy/admin data collision must fail closed in the public view.
        with sqlite3.connect(self.dbpath) as db:
            db.execute(
                "INSERT INTO products(sku,title,description,price_irr,enabled) "
                "VALUES(?,?,?,?,0)",
                ("wheat_seed_rate_v1", "Paid duplicate", "Private draft", 1000))
        html = self.render()
        self.assertNotIn('href="' + URL + '"', html)
        self.assertNotIn("Verified free seed calculator", html)
        self.assertIn("کاتالوگ در حال تکمیل", html)

    def test_tampered_artifact_is_not_advertised(self):
        self.file.write_bytes(b"altered content after verified release")
        html = self.render()
        self.assertNotIn('href="' + URL + '"', html)
        self.assertNotIn("Verified free seed calculator", html)
        self.assertIn("کاتالوگ در حال تکمیل", html)

    def test_missing_artifact_is_not_advertised(self):
        self.file.unlink()
        self.assertNotIn('href="' + URL + '"', self.render())

    def test_symlinked_artifact_is_not_advertised(self):
        other = self.home / "external.html"
        other.write_bytes(self.file.read_bytes())
        self.file.unlink()
        self.file.symlink_to(other)
        self.assertNotIn('href="' + URL + '"', self.render())

    def test_symlinked_product_directory_is_not_advertised(self):
        other = self.home / "outside"
        self.product_dir.rename(other)
        self.product_dir.symlink_to(other, target_is_directory=True)
        self.assertNotIn('href="' + URL + '"', self.render())

    def test_blank_license_cannot_be_publicly_advertised(self):
        self.update("license_text", "   ")
        self.assertNotIn('href="' + URL + '"', self.render())

    def test_wrong_digest_cannot_be_publicly_advertised(self):
        self.update("artifact_sha256", "0" * 64)
        self.assertNotIn('href="' + URL + '"', self.render())

    def test_disabled_record_is_not_publicly_advertised(self):
        self.update("enabled", 0)
        self.assertNotIn('href="' + URL + '"', self.render())

    def test_enabled_paid_draft_is_not_advertised_as_a_public_offer(self):
        # Existing paid rows have no release-rights, fulfillment or merchant proof.
        with sqlite3.connect(self.dbpath) as db:
            db.execute(
                "INSERT INTO products(sku,title,description,price_irr,enabled) VALUES(?,?,?,?,1)",
                ("unverified_paid", "UNVERIFIED_PAID_DRAFT_20261102",
                 "Unreleased draft only", 150000),
            )
        html = self.render()
        self.assertNotIn("UNVERIFIED_PAID_DRAFT_20261102", html)
        self.assertNotIn("150,000", html)
        self.assertIn("خرید آنلاین و برداشت وجه غیرفعال است", html)
        self.assertIn('href="' + URL + '"', html)

    def test_symlinked_private_catalogue_parent_is_rejected(self):
        # A real child directory must not bypass a symlinked .private ancestor.
        redirected = self.home / "private_actual"
        self.private.parent.rename(redirected)
        self.private.parent.symlink_to(redirected, target_is_directory=True)
        html = self.render()
        self.assertIn("Store module is not available", html)
        self.assertNotIn('href="' + URL + '"', html)

    def test_symlinked_private_php_module_is_never_executed(self):
        marker = self.home / "malicious_module_ran"
        outside = self.home / "outside_site_store.php"
        outside.write_text("<?php file_put_contents(" + repr(str(marker)) + ", 'bad');",
                           encoding="utf8")
        module = self.private / "site_store.php"
        module.unlink()
        module.symlink_to(outside)
        html = self.render()
        self.assertIn("Store module is not available", html)
        self.assertFalse(marker.exists())

    def test_private_free_status_follows_real_release_integrity(self):
        with sqlite3.connect(self.dbpath) as db:
            db.execute("""CREATE TABLE payment_state
                (id INTEGER PRIMARY KEY, provider TEXT, state TEXT, note TEXT)""")
            db.execute("""INSERT INTO payment_state VALUES
                (1,'Bank Shahr','not_configured','No live payment')""")
        script = self.home / "private_status.php"
        script.write_text(r"""<?php
function role(){return 'viewer';}
function esc($x){return htmlspecialchars((string)$x,ENT_QUOTES,'UTF-8');}
function tokenInput(){return '';}
require $argv[1];
$db=zmStorePublicDb($argv[2]);
zmStoreRender($db);
""", encoding="utf8")

        def status():
            run = subprocess.run(
                ["php", str(script), str(self.private / "site_store.php"),
                 str(self.private)],
                capture_output=True, text=True, timeout=15)
            self.assertEqual(run.returncode, 0, run.stderr)
            return run.stdout

        self.assertIn("فایل معتبر؛ قابل نمایش عمومی", status())
        self.file.write_bytes(b"changed after original release")
        self.assertIn("غیرفعال یا فایل/مجوز نامعتبر", status())
        self.assertNotIn("فایل معتبر؛ قابل نمایش عمومی", status())
        self.file.write_bytes(b"verified original free release")
        self.update("license_text", "  ")
        self.assertIn("غیرفعال یا فایل/مجوز نامعتبر", status())

    def test_admin_cannot_enable_unverified_paid_draft_but_can_withdraw(self):
        # The legacy toggle may withdraw a published row, not create a paid offer.
        php = r"""<?php
function req($name) { return $name==='product_id' ? '1' : ''; }
function bail($message) { throw new RuntimeException($message); }
require $argv[1];
$db=zmStoreDb($argv[2]);
$db->exec("INSERT INTO products(id,sku,title,description,price_irr,enabled) VALUES(1,'draft','Draft','No proof',1000,0)");
try { zmStoreHandle($db,'product_toggle'); exit(41); }
catch(RuntimeException $e) {}
if((int)$db->query("SELECT enabled FROM products WHERE id=1")->fetchColumn()!==0)exit(42);
$db->exec("UPDATE products SET enabled=1 WHERE id=1");
zmStoreHandle($db,'product_toggle');
if((int)$db->query("SELECT enabled FROM products WHERE id=1")->fetchColumn()!==0)exit(43);
echo "PAID_RELEASE_GATE=PASS";
"""
        script = self.home / "paid_gate.php"
        script.write_text(php, encoding="utf8")
        run = subprocess.run(
            ["php", str(script), str(self.private / "site_store.php"), str(self.private)],
            capture_output=True, text=True, timeout=15)
        self.assertEqual(run.returncode, 0, run.stderr + run.stdout)
        self.assertIn("PAID_RELEASE_GATE=PASS", run.stdout)



    def test_public_store_restricts_browser_privileges(self):
        # Real local HTTP response: CLI headers_list() is not reliable for this check.
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        server = subprocess.Popen(
            ["php", "-S", f"127.0.0.1:{port}", "-t", str(self.home / "public_html")],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            response = None
            for _ in range(40):
                try:
                    response = urllib.request.urlopen(
                        f"http://127.0.0.1:{port}/store/index.php", timeout=2)
                    break
                except urllib.error.URLError:
                    time.sleep(0.1)
            self.assertIsNotNone(response, "Local PHP server did not start")
            with response:
                self.assertEqual(response.status, 200)
                self.assertIn("default-src 'none'",
                              response.headers.get("Content-Security-Policy", ""))
                self.assertIn("frame-ancestors 'none'",
                              response.headers.get("Content-Security-Policy", ""))
                self.assertEqual(response.headers.get("X-Frame-Options"), "DENY")
                self.assertEqual(response.headers.get("Referrer-Policy"), "no-referrer")
                self.assertEqual(response.headers.get("Cache-Control"),
                                 "private, no-store, max-age=0")
        finally:
            server.terminate()
            server.wait(timeout=5)

    def test_private_paid_rows_never_claim_public_sales_readiness(self):
        php = r"""<?php
function role(){return 'viewer';}
function esc($s){return htmlspecialchars((string)$s, ENT_QUOTES, 'UTF-8');}
function tokenInput(){return '';}
require $argv[1];
$db=zmStoreDb($argv[2]);
$db->exec("INSERT INTO products(id,sku,title,description,price_irr,enabled)
           VALUES(1,'legacy','Legacy paid','Private only',1000,1)");
ob_start();
zmStoreRender($db);
$html=ob_get_clean();
if(strpos($html,'ردیف قدیمی؛ عرضه عمومی مسدود')===false)exit(51);
if(strpos($html,'<td>فعال</td>')!==false)exit(52);
if(strpos($html,'وضعیت ثبت خصوصی')===false)exit(53);
echo 'PRIVATE_PAID_STATUS=PASS';
"""
        script = self.home / "admin_status.php"
        script.write_text(php, encoding="utf8")
        run = subprocess.run(
            ["php", str(script), str(self.private / "site_store.php"), str(self.private)],
            capture_output=True, text=True, timeout=15)
        self.assertEqual(run.returncode, 0, run.stderr + run.stdout)
        self.assertIn("PRIVATE_PAID_STATUS=PASS", run.stdout)


    def test_paid_draft_rejects_free_product_sku_collision(self):
        php = r"""<?php
$sku='shared_catalog_sku';
function req($name){
  global $sku;
  $v=['sku'=>$sku,'title'=>'Paid draft','description'=>'Private draft','price_irr'=>'1500'];
  return $v[$name]??'';
}
function mbSafeLen($s){return strlen($s);}
function bail($message){throw new RuntimeException($message);}
require $argv[1];
$db=zmStoreDb($argv[2]);
$db->exec("INSERT INTO free_digital_products
 (sku,title,description,download_path,artifact_sha256,license_text,price_irr,enabled)
 VALUES('shared_catalog_sku','Free','Existing','/store/free-products/free/index.html',
 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa','Free use',0,0)");
try {zmStoreHandle($db,'product_create');exit(61);}
catch(RuntimeException $e){}
if((int)$db->query('SELECT COUNT(*) FROM products')->fetchColumn()!==0)exit(62);
$sku='unique_paid_draft';
zmStoreHandle($db,'product_create');
$row=$db->query("SELECT sku,enabled FROM products LIMIT 1")->fetch(PDO::FETCH_ASSOC);
if(!$row||$row['sku']!=='unique_paid_draft'||(int)$row['enabled']!==0)exit(63);
echo 'CROSS_CATALOG_SKU=PASS';
"""
        script = self.home / "sku_collision.php"
        script.write_text(php, encoding="utf8")
        run = subprocess.run(
            ["php", str(script), str(self.private / "site_store.php"), str(self.private)],
            capture_output=True, text=True, timeout=15)
        self.assertEqual(run.returncode, 0, run.stderr + run.stdout)
        self.assertIn("CROSS_CATALOG_SKU=PASS", run.stdout)



    def test_sqlite_prevents_cross_catalog_sku_collisions_from_other_writers(self):
        # Enforce the rule in SQLite itself, including imports and SKU updates.
        php = r"""<?php
require $argv[1];
$db=zmStoreDb($argv[2]);
$db->exec("INSERT INTO free_digital_products
 (sku,title,description,download_path,artifact_sha256,license_text)
 VALUES('free_only','Free','Verified','/store/free-products/free/index.html',
 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa','Free use')");
$db->exec("INSERT INTO products(sku,title,description,price_irr)
 VALUES('paid_only','Paid','Private',1000)");
$bad=[
 "INSERT INTO products(sku,title,description,price_irr) VALUES('free_only','Bad','Bad',1000)",
 "INSERT INTO free_digital_products(sku,title,description,download_path,artifact_sha256,license_text) VALUES('paid_only','Bad','Bad','/store/free-products/bad/index.html','bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb','Free')",
 "UPDATE products SET sku='free_only' WHERE sku='paid_only'",
 "UPDATE free_digital_products SET sku='paid_only' WHERE sku='free_only'",
];
foreach($bad as $sql){
 try{$db->exec($sql);exit(71);}catch(PDOException $e){
  if(strpos($e->getMessage(),'cross_catalog_sku_collision')===false)exit(72);
 }
}
if((int)$db->query('SELECT COUNT(*) FROM products')->fetchColumn()!==1)exit(73);
if((int)$db->query('SELECT COUNT(*) FROM free_digital_products')->fetchColumn()!==1)exit(74);
echo 'CROSS_CATALOG_SQLITE_GUARDS=PASS';
"""
        script = self.home / "sku_triggers.php"
        script.write_text(php, encoding="utf8")
        run = subprocess.run(
            ["php", str(script), str(self.private / "site_store.php"), str(self.private)],
            capture_output=True, text=True, timeout=15)
        self.assertEqual(run.returncode, 0, run.stderr + run.stdout)
        self.assertIn("CROSS_CATALOG_SQLITE_GUARDS=PASS", run.stdout)

    def test_product_toggle_rejects_noncanonical_ids_without_touching_row(self):
        php = r"""<?php
$id='1junk';
function req($name){global $id;return $id;}
function bail($message){throw new RuntimeException($message);}
require $argv[1];
$db=zmStoreDb($argv[2]);
$db->exec("INSERT INTO products(id,sku,title,description,price_irr,enabled)
 VALUES(1,'paid_draft','Paid','Private',1000,1)");
foreach(['1junk','1.0','01','9223372036854775808','-1'] as $candidate){
 $id=$candidate;
 try{zmStoreHandle($db,'product_toggle');exit(81);}catch(RuntimeException $e){}
 if((int)$db->query('SELECT enabled FROM products WHERE id=1')->fetchColumn()!==1)exit(82);
}
$id='1';
zmStoreHandle($db,'product_toggle');
if((int)$db->query('SELECT enabled FROM products WHERE id=1')->fetchColumn()!==0)exit(83);
echo 'STRICT_PRODUCT_ID=PASS';
"""
        script = self.home / "strict_product_id.php"
        script.write_text(php, encoding="utf8")
        run = subprocess.run(
            ["php", str(script), str(self.private / "site_store.php"), str(self.private)],
            capture_output=True, text=True, timeout=15)
        self.assertEqual(run.returncode, 0, run.stderr + run.stdout)
        self.assertIn("STRICT_PRODUCT_ID=PASS", run.stdout)


if __name__ == "__main__":
    unittest.main()
