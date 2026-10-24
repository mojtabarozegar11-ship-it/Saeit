"""Offline regression for the separate site master customer order/question inboxes."""
import importlib.util
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest import mock

FILE = Path(__file__).resolve().parents[1] / "scripts/site_master_customer_runtime_20261024.py"
SPEC = importlib.util.spec_from_file_location("site_master_customer_runtime_20261024", FILE)
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


class CustomerInboxTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.zm = self.base / "zomorod"
        self.mpw = self.base / "mpw"
        for path in (self.zm, self.mpw):
            path.mkdir(mode=0o700)
            path.chmod(0o700)
        self.saved = dict(mod.CONFIG)
        self.addCleanup(self._restore)
        mod.CONFIG["zomorod"] = {"root": self.zm, "source": self.zm / "site_store.sqlite3"}
        mod.CONFIG["mojplaywin"] = {"root": self.mpw, "django": self.mpw}

    def _restore(self):
        mod.CONFIG.clear()
        mod.CONFIG.update(self.saved)

    def make_db(self, tenant):
        root = self.zm if tenant == "zomorod" else self.mpw
        path = root / "master_customer_inbox.sqlite3"
        conn = sqlite3.connect(str(path))
        conn.execute("CREATE TABLE customer_questions(id TEXT PRIMARY KEY,tenant TEXT,kind TEXT,full_name TEXT,email TEXT,question TEXT,claimed_order_ref TEXT,initial_reply TEXT,processing_status TEXT,created_utc TEXT DEFAULT CURRENT_TIMESTAMP,master_processed_utc TEXT)")
        conn.execute("CREATE TABLE customer_order_events(id INTEGER PRIMARY KEY,tenant TEXT,source TEXT,source_id TEXT,source_status TEXT,event_digest TEXT,seen_utc TEXT DEFAULT CURRENT_TIMESTAMP,UNIQUE(tenant,source,source_id,event_digest))")
        conn.commit()
        conn.close()
        path.chmod(0o600)
        return mod.open_inbox(tenant)

    def test_idempotent_order_state_changes_separate_sites(self):
        a = self.make_db("zomorod")
        b = self.make_db("mojplaywin")
        self.assertTrue(mod.project_order(a, "zomorod", "orders", 101, "pending"))
        self.assertFalse(mod.project_order(a, "zomorod", "orders", 101, "pending"))
        self.assertTrue(mod.project_order(a, "zomorod", "orders", 101, "paid"))
        self.assertTrue(mod.project_order(b, "mojplaywin", "core_order", 101, "paid"))
        a.commit(); b.commit()
        self.assertEqual(a.execute("SELECT COUNT(*) FROM customer_order_events").fetchone()[0], 2)
        self.assertEqual(b.execute("SELECT COUNT(*) FROM customer_order_events").fetchone()[0], 1)
        a.close();b.close()

    def test_orders_cannot_supply_untrusted_source_or_status(self):
        db=self.make_db("zomorod")
        for source,key,state in (("other.site",1,"paid"),("orders","bad;drop","paid"),("orders",2,"paid; DELETE")):
            with self.assertRaises(ValueError):
                mod.project_order(db,"zomorod",source,key,state)
        self.assertEqual(db.execute("SELECT COUNT(*) FROM customer_order_events").fetchone()[0],0)
        db.close()

    def test_native_question_ticket_deduplicated(self):
        db=self.make_db("mojplaywin")
        self.assertTrue(mod.project_question(db,"mojplaywin","company_inquiry",7,"M.","a@example.com","Help me with delivery"))
        self.assertFalse(mod.project_question(db,"mojplaywin","company_inquiry",7,"M.","a@example.com","Help me with delivery"))
        self.assertEqual(db.execute("SELECT COUNT(*) FROM customer_questions").fetchone()[0],1)
        with self.assertRaises(ValueError):
            mod.project_question(db,"mojplaywin","other_site",7,"","", "data")
        db.close()

    def test_store_orders_source_read_only(self):
        db=self.make_db("zomorod")
        source=self.zm/"site_store.sqlite3"
        with sqlite3.connect(str(source)) as store:
            store.execute("CREATE TABLE orders(id INTEGER PRIMARY KEY,status TEXT)")
            store.execute("INSERT INTO orders VALUES(1,'pending'),(2,'paid')")
        result=mod.import_zomorod_order_ledger(db)
        self.assertEqual(result["source"],"local_store_ledger")
        self.assertEqual(result["orders"],2)
        self.assertEqual(mod.import_zomorod_order_ledger(db)["orders"],0)
        with sqlite3.connect(str(source)) as store:
            self.assertEqual(store.execute("SELECT COUNT(*) FROM orders").fetchone()[0],2)
        db.close()

    def test_private_db_and_symlink_guards(self):
        db=self.make_db("zomorod");db.close()
        self.zm.chmod(0o707)
        with self.assertRaises(RuntimeError):
            mod.open_inbox("zomorod")
        self.zm.chmod(0o700)
        (self.zm/"master_customer_inbox.sqlite3").chmod(0o644)
        with self.assertRaises(RuntimeError):
            mod.open_inbox("zomorod")
        with self.assertRaises(ValueError):
            mod.safe_root("unknown")

    def test_run_does_not_mark_queue_if_real_master_fails(self):
        db=self.make_db("zomorod")
        mod.project_question(db,"zomorod","company_inquiry",9,"A","a@example.com","Where is the order")
        db.commit();db.close()
        with mock.patch.object(mod,"master_callback",side_effect=RuntimeError("offline_master_failed")):
            with self.assertRaisesRegex(RuntimeError,"offline_master_failed"):
                mod.run("zomorod")
        with mod.open_inbox("zomorod") as check:
            self.assertEqual(check.execute("SELECT processing_status FROM customer_questions").fetchone()[0],"queued")


    def test_financial_and_delivery_requests_cannot_be_marked_resolved(self):
        cases = (
            ("order_question", "How can I get a coupon?"),
            ("question", "Where is my paid order?"),
            ("question", "Please refund my purchase"),
            ("question", "My download file is missing"),
            ("question", "پیگیری پرداخت سفارش"),
            ("question", "درخواست استرداد وجه"),
            ("question", "مشکل دانلود فایل"),
            ("question", "Please help with a delivery discount"),
            ("question", "Can you verify my TRX transfer"),
        )
        for kind, question in cases:
            with self.subTest(question=question):
                self.assertEqual(mod.classify_customer_ticket(kind,question),"needs_review")
        self.assertEqual(mod.classify_customer_ticket("question","What is the coupon policy?"),"handled")
        self.assertEqual(mod.classify_customer_ticket("question","قانون تخفیف چگونه است؟"),"handled")
        self.assertEqual(mod.classify_customer_ticket("question","Who are you?"),"needs_review")

    def test_master_health_heartbeat_and_real_pending_review_counts(self):
        db = self.make_db("zomorod")
        for pk,question in enumerate(("Please refund my order","Coupon policy please",
                                     "Unknown product composition"),1):
            mod.project_question(db,"zomorod","company_inquiry",pk,"Customer","test@example.com",question)
        db.execute(
            "UPDATE customer_questions SET created_utc=datetime('now','-2 day') WHERE id=?",
            ("native-company_inquiry-1",)
        )
        db.commit()
        db.close()
        with mock.patch.object(mod,"master_callback",return_value=None):
            result=mod.run("zomorod")
        self.assertEqual(result["questions_processed"],3)
        self.assertEqual(result["review_waiting"],2)
        self.assertEqual(result["review_older_than_day"],1)
        self.assertEqual(result["guidance_processed"],1)
        with mod.open_inbox("zomorod") as checked:
            states=dict(checked.execute("SELECT question,processing_status FROM customer_questions"))
            self.assertEqual(states["Please refund my order"],"needs_review")
            self.assertEqual(states["Coupon policy please"],"handled")
            self.assertEqual(states["Unknown product composition"],"needs_review")
            pulse=checked.execute("SELECT queued,review,guidance,review_older_than_day FROM master_customer_worker_health WHERE tenant='zomorod'").fetchone()
            self.assertEqual(pulse,(0,2,1,1))
        with mock.patch.object(mod,"master_callback",return_value=None):
            again=mod.run("zomorod")
        self.assertEqual(again["questions_processed"],0)
        self.assertEqual(again["review_waiting"],2)


if __name__=="__main__":
    unittest.main()
