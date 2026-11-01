"""Regression: PHP business stock must never oversell under concurrent requests.

All runtime fixtures use a fresh temporary SQLite database and PHP session files.
No production database, cPanel, external network, or customer data is accessed.
"""
import concurrent.futures
import shutil
import sqlite3
import subprocess
import tempfile
import unittest
from pathlib import Path


SOURCE = Path(__file__).resolve().parents[1] / "content" / "zomorod-business" / "app.php"
PHP = shutil.which("php")


def php_has_sqlite():
    if not PHP:
        return False
    result = subprocess.run(
        [PHP, "-r", "echo extension_loaded('pdo_sqlite') ? 'yes' : 'no';"],
        capture_output=True, text=True, timeout=10, check=True
    )
    return result.stdout == "yes"


class StockMovementRegression(unittest.TestCase):
    def test_source_contract_and_php_lint(self):
        source = SOURCE.read_text(encoding="utf-8")
        block = source.split("} elseif($action==='stock'){", 1)[1].split(
            "} elseif($action==='employee'){", 1
        )[0]
        self.assertIn("$db->exec('BEGIN IMMEDIATE')", block)
        self.assertIn("if($now+$qty<0)", block)
        self.assertIn("audit($db,'move','inventory-stock'", block)
        self.assertLess(block.index("audit($db,'move'"), block.index("$db->commit()"))
        self.assertIn("if($db->inTransaction())$db->rollBack()", block)
        self.assertIn("preg_match('/^-?(?:0|[1-9][0-9]{0,8})$/D'", block)
        if PHP:
            result = subprocess.run([PHP, "-l", str(SOURCE)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)

    @unittest.skipUnless(PHP and php_has_sqlite(), "PHP pdo_sqlite unavailable")
    def test_concurrent_outbound_requests_and_malformed_quantity(self):
        with tempfile.TemporaryDirectory(prefix="zm-stock-") as tmp:
            home = Path(tmp)
            private = home / ".private" / "zomorod-business"
            private.mkdir(parents=True)
            sessions = home / "sessions"
            sessions.mkdir()
            app = private / "app.php"
            shutil.copy2(SOURCE, app)
            init_script = (
                "$_SERVER['REQUEST_METHOD']='GET'; "
                "$_GET['page']='dashboard'; require " + repr(str(app)) + ";"
            )
            subprocess.run(
                [PHP, "-d", f"session.save_path={sessions}", "-r", init_script],
                check=True, capture_output=True, timeout=20
            )
            dbpath = private / "management.sqlite3"
            with sqlite3.connect(dbpath) as db:
                db.execute(
                    "INSERT INTO users(id,username,password_hash,role,active) "
                    "VALUES(1,'test_admin','not-a-password','admin',1)"
                )
                db.execute(
                    "INSERT INTO inventory(id,sku,name) VALUES(1,'TEST-1','fixture')"
                )
                db.execute(
                    "INSERT INTO inventory_movements"
                    "(inventory_id,movement_date,qty,note,created_by) "
                    "VALUES(1,'2026-11-01',10,'seed',1)"
                )
                db.commit()

            def post(qty, sid):
                # Isolated authenticated sessions, identical stock item.
                script = (
                    "ini_set('session.save_path'," + repr(str(sessions)) + ");"
                    "session_name('ZM_BUSINESS');"
                    "session_id(" + repr(sid) + ");session_start();"
                    "$_SESSION['uid']=1;$_SESSION['role']='admin';"
                    "$_SESSION['csrf']=str_repeat('a',64);session_write_close();"
                    "$_SERVER['REQUEST_METHOD']='POST';"
                    "$_GET['page']='inventory';"
                    "$_POST=['action'=>'stock','csrf'=>str_repeat('a',64),"
                    "'inventory_id'=>'1','qty'=>" + repr(qty) + ","
                    "'date'=>'2026-11-01','note'=>'regression'];"
                    "require " + repr(str(app)) + ";"
                )
                return subprocess.run(
                    [PHP, "-d", f"session.save_path={sessions}", "-r", script],
                    capture_output=True, text=True, timeout=30
                )

            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                outcomes = list(pool.map(lambda v: post("-8", f"testsession{v}"), (1, 2)))
            for outcome in outcomes:
                self.assertEqual(outcome.returncode, 0, outcome.stderr)
            with sqlite3.connect(dbpath) as db:
                stock = db.execute(
                    "SELECT SUM(qty) FROM inventory_movements WHERE inventory_id=1"
                ).fetchone()[0]
                moves = db.execute(
                    "SELECT COUNT(*) FROM inventory_movements WHERE qty=-8"
                ).fetchone()[0]
                audits = db.execute(
                    "SELECT COUNT(*) FROM audit_events WHERE subject='inventory-stock'"
                ).fetchone()[0]
            self.assertEqual(stock, 2)
            self.assertEqual(moves, 1)
            self.assertEqual(audits, 1)

            post("2abc", "testsessioninvalid")
            with sqlite3.connect(dbpath) as db:
                self.assertEqual(
                    db.execute("SELECT COUNT(*) FROM inventory_movements").fetchone()[0], 2
                )


if __name__ == "__main__":
    unittest.main()
