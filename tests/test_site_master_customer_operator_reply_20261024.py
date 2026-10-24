"""Safety checks for staff-reviewed responses in independent site masters."""
from pathlib import Path
import importlib.util
import sqlite3
import unittest

MODULE = Path(__file__).resolve().parents[1] / "scripts/site_master_customer_operator_reply_20261024.py"
SPEC = importlib.util.spec_from_file_location("site_master_operator_reply", MODULE)
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


class OperatorReviewTests(unittest.TestCase):
    def make_db(self):
        db = sqlite3.connect(":memory:")
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("CREATE TABLE customer_questions(id TEXT PRIMARY KEY,tenant TEXT,processing_status TEXT)")
        return db

    def test_only_real_review_ticket_can_receive_reply(self):
        db=self.make_db()
        a="a"*24
        db.execute("INSERT INTO customer_questions VALUES(?,?,?)",(a,"zomorod","needs_review"))
        self.assertEqual(mod.save_reply(db,"zomorod",a,"Staff has reviewed your request.","operator"),"stored")
        self.assertEqual(mod.save_reply(db,"zomorod",a,"Staff has reviewed your request.","operator"),"already_recorded")
        self.assertEqual(db.execute("SELECT COUNT(*) FROM customer_operator_replies").fetchone()[0],1)
        with self.assertRaisesRegex(RuntimeError,"NO_OVERWRITE"):
            mod.save_reply(db,"zomorod",a,"A DIFFERENT response after review.","operator")
        self.assertEqual(db.execute("SELECT answer FROM customer_operator_replies").fetchone()[0],"Staff has reviewed your request.")
        db.close()

    def test_reject_unverified_queued_tenant_and_invalid_input(self):
        db=self.make_db()
        a="b"*24
        db.execute("INSERT INTO customer_questions VALUES(?,?,?)",(a,"zomorod","queued"))
        for site,ticket,answer,reviewer in (
            ("zomorod",a,"Staff response awaits verification.","operator"),
            ("mojplaywin",a,"Staff response awaits verification.","operator"),
            ("zomorod","not-a-ticket","Staff response awaits verification.","operator"),
            ("other_site",a,"Staff response awaits verification.","operator"),
            ("zomorod",a,"short","operator"),
            ("zomorod",a,"Staff response awaits verification.","admin;drop"),
        ):
            with self.subTest(site=site,ticket=ticket,answer=answer):
                with self.assertRaises(RuntimeError):
                    mod.save_reply(db,site,ticket,answer,reviewer)
        self.assertEqual(db.execute("SELECT name FROM sqlite_master WHERE name='customer_operator_replies'").fetchone(),None)
        db.close()

    def test_never_mutates_native_order_records(self):
        db=self.make_db()
        db.execute("CREATE TABLE native_order(id INTEGER PRIMARY KEY,status TEXT)")
        db.execute("INSERT INTO native_order VALUES(99,'paid')")
        ticket="f"*24
        db.execute("INSERT INTO customer_questions VALUES(?,?,?)",(ticket,"mojplaywin","needs_review"))
        self.assertEqual(mod.save_reply(db,"mojplaywin",ticket,"We have your question and will respond.","operator"),"stored")
        self.assertEqual(db.execute("SELECT status FROM native_order WHERE id=99").fetchone()[0],"paid")
        db.close()


if __name__=="__main__":
    unittest.main()
