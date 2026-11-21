"""Offline synthetic tests: no production access or network."""
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from integrations.zomorod_business_readonly.bridge_app import create_app


class ReadOnlyBridgeTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.path = Path(t.name) / "management.sqlite3"
        with sqlite3.connect(self.path) as db:
            db.executescript("""
            CREATE TABLE projects(id INTEGER,title TEXT,owner TEXT,state TEXT,budget INTEGER);
            CREATE TABLE invoices(id INTEGER,currency TEXT,kind TEXT,amount INTEGER,due_date TEXT);
            CREATE TABLE invoice_payments(invoice_id INTEGER,amount INTEGER);
            CREATE TABLE inventory(id INTEGER,sku TEXT,name TEXT,unit TEXT,reorder_level INTEGER);
            CREATE TABLE inventory_movements(inventory_id INTEGER,qty INTEGER);
            INSERT INTO projects VALUES(191,'Synthetic','Test','planned',0);
            INSERT INTO invoices VALUES(1,'IRR','sale',1000,'2000-01-01');
            INSERT INTO invoice_payments VALUES(1,400);
            INSERT INTO inventory VALUES(1,'SYN-1','Demo','unit',2);
            INSERT INTO inventory_movements VALUES(1,5);
            INSERT INTO inventory_movements VALUES(1,-1);
            """)
        self.token = "Z" * 48
        self.cfg = dict(ZM_RO_BRIDGE_DB=str(self.path),
                        ZM_RO_BRIDGE_TOKEN_SHA256=hashlib.sha256(self.token.encode()).hexdigest(),
                        ZM_RO_BRIDGE_ALLOWED_IPS="127.0.0.1/32",
                        DOCUMENT_ROOT=str(Path(t.name) / "public_html"))
        self.base = dict(wsgi_url_scheme="https", REMOTE_ADDR="127.0.0.1",
                         REQUEST_METHOD="GET", HTTP_AUTHORIZATION="Bearer " + self.token,
                         PATH_INFO="/v1/health", QUERY_STRING="")

    def query(self, cfg=None, **updates):
        status = []
        def start(code, headers):
            status.append((code, dict(headers)))
        env = {**self.base, **updates}
        env["wsgi.url_scheme"] = env.pop("wsgi_url_scheme", "https")
        output = b"".join(create_app(self.cfg if cfg is None else cfg)(env, start))
        return status[0], json.loads(output)

    def test_fail_closed(self):
        self.assertEqual(self.query(cfg={})[0][0], "404 Not Found")
        self.assertEqual(self.query(wsgi_url_scheme="http")[0][0], "404 Not Found")
        self.assertEqual(self.query(REMOTE_ADDR="198.51.100.5")[0][0], "403 Forbidden")
        self.assertEqual(self.query(HTTP_AUTHORIZATION="")[0][0], "401 Unauthorized")
        self.assertEqual(self.query(HTTP_AUTHORIZATION="Bearer " + "X"*48)[0][0], "401 Unauthorized")
        self.assertEqual(self.query(REQUEST_METHOD="POST")[0][0], "405 Method Not Allowed")
        self.assertEqual(self.query(cfg={**self.cfg, "ZM_RO_BRIDGE_ALLOWED_IPS":"invalid"})[0][0],
                         "404 Not Found")

    def test_health_is_private_and_not_cached(self):
        (status, headers), data = self.query()
        self.assertEqual(status, "200 OK")
        self.assertEqual(data["access"], "read_only")
        self.assertEqual(headers["Cache-Control"], "no-store, max-age=0")
        self.assertNotIn("Access-Control-Allow-Origin", headers)

    def test_projects_do_not_mutate_source(self):
        before = hashlib.sha256(self.path.read_bytes()).digest()
        (_, _), data = self.query(PATH_INFO="/v1/projects")
        self.assertEqual(data["projects"][0]["id"], 191)
        self.assertEqual(hashlib.sha256(self.path.read_bytes()).digest(), before)

    def test_money_is_not_converted(self):
        (_, _), data = self.query(PATH_INFO="/v1/finance-summary")
        row = data["by_currency_and_kind"][0]
        self.assertEqual(row["amount_stored_integer"], 1000)
        self.assertEqual(row["paid_stored_integer"], 400)
        self.assertEqual(row["unpaid_stored_integer"], 600)
        self.assertEqual(row["overdue_stored_integer"], 600)

    def test_stock(self):
        (_, _), data = self.query(PATH_INFO="/v1/inventory")
        self.assertEqual(data["inventory"][0]["on_hand"], 4)

    def test_no_other_routes_or_unbounded_queries(self):
        self.assertEqual(self.query(PATH_INFO="/v1/users")[0][0], "404 Not Found")
        self.assertEqual(self.query(QUERY_STRING="limit=101")[0][0], "400 Bad Request")
        self.assertEqual(self.query(QUERY_STRING="limit=-1")[0][0], "400 Bad Request")
        self.assertEqual(self.query(QUERY_STRING="sql=DROP")[0][0], "400 Bad Request")

    def test_missing_db_not_created(self):
        missing = self.path.parent / "missing" / "management.sqlite3"
        self.assertEqual(self.query(cfg={**self.cfg,"ZM_RO_BRIDGE_DB":str(missing)})[0][0],
                         "503 Service Unavailable")
        self.assertFalse(missing.exists())

    def test_public_db_blocked(self):
        self.assertEqual(self.query(cfg={**self.cfg,"DOCUMENT_ROOT":str(self.path.parent)})[0][0],
                         "404 Not Found")


if __name__ == "__main__":
    unittest.main()
