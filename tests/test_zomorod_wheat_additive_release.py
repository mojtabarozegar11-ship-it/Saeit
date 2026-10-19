"""Isolated live-free-landing publication regression: paid commerce is immutable."""
import importlib.util
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/zomorod_wheat_additive_release.py"
CURRENT_INDEX = ROOT / "content/zomorod-v11/store_index.php"
OLDER_SHA_BASE = "ed8889b108ebf229d7682d77208104d0367032026a34e70c31cf7f3b5dbd91ff"

spec = importlib.util.spec_from_file_location("wheat_release", SCRIPT)
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class TestWheatAdditive(unittest.TestCase):
    def test_pinned_existing_live_baseline(self):
        self.assertEqual(release.LIVE_INDEX_SHA, OLDER_SHA_BASE)
        self.assertEqual(len(release.LIVE_LIB_SHA), 64)
        self.assertEqual(release.SKU, "wheat_seed_rate_v1")
        self.assertEqual(release.DOWNLOAD, "/store/free-products/wheat-seed-rate-planner-v1/index.html")

    def test_candidate_preserves_paid_catalog_and_original_store_footer(self):
        # Fixture is the isolated original paid storefront; new remote live code
        # is pinned separately by SHA-256 before ever calling this function.
        file = CURRENT_INDEX.read_text(encoding="utf8")
        file=file.replace("if(!$items && !$free) echo", "if(!$items) echo")
        start=file.index("foreach($free as $p)")
        end=file.index("foreach($items as $p)")
        file=file[:start]+file[end:]
        file=file.replace("$free=$db->query('SELECT title,description,sku,download_path,artifact_sha256,license_text FROM free_digital_products WHERE enabled=1 ORDER BY id DESC LIMIT 100')->fetchAll();", "")
        file=file.replace("free_digital_products WHERE enabled=1", "paid_database_unchanged")
        # Input might be a different staging schema; exercise immutable specific anchors.
        file = (file[:file.find("if(!$items) echo")] + file[file.find("if(!$items) echo"):]
                if "if(!$items) echo" in file else file)
        candidate=release.build_candidate(file)
        self.assertEqual(candidate.count(release.MARK),1)
        self.assertEqual(candidate.count(release.PAID_CARD),1)
        self.assertIn("if(!$items && !$free) echo",candidate)
        self.assertIn("free_digital_products WHERE enabled=1",candidate)
        self.assertIn("پرداخت آنلاین تا اتصال درگاه غیرفعال است",candidate)

    def test_safe_fail_closed_on_unrecognized_body(self):
        with self.assertRaisesRegex(RuntimeError,"UNKNOWN_PUBLIC_STORE_TEMPLATE"):
            release.build_candidate("<?php echo 'unrelated';")
        body="function storeEsc(abc){}\nif(!$items) echo 'empty';\nforeach($items as $p){echo 'paid';"
        result=release.build_candidate(body)
        self.assertIn(release.MARK,result)
        with self.assertRaisesRegex(RuntimeError,"FREE_CATALOG_ALREADY_EDITED"):
            release.build_candidate(result)

    @unittest.skipUnless(shutil.which("php"),"PHP required")
    def test_php_additive_candidate_syntax(self):
        original="""<?php
        function storeEsc(string $x):string{return htmlspecialchars($x,ENT_QUOTES,'UTF-8');}
        $db=new PDO('sqlite::memory:');$db->exec("create table free_digital_products(id integer, enabled integer, title text, description text,sku text, download_path text,artifact_sha256 text,license_text text)");
        $items=[];
        if(!$items) echo '<section>empty</section>';
        foreach($items as $p){echo '<div>paid</div>';}
        """
        candidate=release.build_candidate(original)
        with tempfile.TemporaryDirectory() as folder:
            file=Path(folder)/"check.php"
            file.write_text(candidate,encoding="utf8")
            p=subprocess.run(["php","-l",str(file)],capture_output=True,text=True,timeout=5)
        self.assertEqual(p.returncode,0,p.stderr)


if __name__=="__main__":
    unittest.main()
