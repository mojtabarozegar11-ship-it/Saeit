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
        db.execute("CREATE TABLE customer_questions(id TEXT PRIMARY KEY,tenant TEXT,processing_status TEXT,master_processed_utc TEXT,kind TEXT DEFAULT 'question',question TEXT DEFAULT 'Sample question',claimed_order_ref TEXT DEFAULT '',created_utc TEXT DEFAULT CURRENT_TIMESTAMP)")
        return db

    def test_only_real_review_ticket_can_receive_reply(self):
        db=self.make_db()
        a="a"*24
        db.execute("INSERT INTO customer_questions(id,tenant,processing_status,master_processed_utc) VALUES(?,?,?,?)",(a,"zomorod","needs_review",None))
        self.assertEqual(mod.save_reply(db,"zomorod",a,"Staff has reviewed your request.","operator"),"stored")
        self.assertEqual(mod.save_reply(db,"zomorod",a,"Staff has reviewed your request.","operator"),"already_recorded")
        self.assertEqual(db.execute("SELECT COUNT(*) FROM customer_operator_replies").fetchone()[0],1)
        self.assertEqual(db.execute("SELECT processing_status FROM customer_questions WHERE id=?", (a,)).fetchone()[0],"handled")
        self.assertEqual(mod.list_pending_reviews(db,"zomorod"),[])

        with self.assertRaisesRegex(RuntimeError,"NO_OVERWRITE"):
            mod.save_reply(db,"zomorod",a,"A DIFFERENT response after review.","operator")
        self.assertEqual(db.execute("SELECT answer FROM customer_operator_replies").fetchone()[0],"Staff has reviewed your request.")
        db.close()

    def test_reject_unverified_queued_tenant_and_invalid_input(self):
        db=self.make_db()
        a="b"*24
        db.execute("INSERT INTO customer_questions(id,tenant,processing_status,master_processed_utc) VALUES(?,?,?,?)",(a,"zomorod","queued",None))
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

    def test_private_queue_excludes_answered_reviews_and_other_tenant(self):
        db=self.make_db()
        a,b,c="1"*24,"2"*24,"3"*24
        for ticket,tenant in ((a,"zomorod"),(b,"zomorod"),(c,"mojplaywin")):
            db.execute("INSERT INTO customer_questions(id,tenant,processing_status,master_processed_utc) VALUES(?,?,?,?)",
                       (ticket,tenant,"needs_review",None))
        self.assertEqual([row[0] for row in mod.list_pending_reviews(db,"zomorod")],[a,b])
        self.assertEqual(mod.save_reply(db,"zomorod",a,
                         "Our support team has provided this final answer.","operator"),"stored")
        self.assertEqual([row[0] for row in mod.list_pending_reviews(db,"zomorod")],[b])
        self.assertEqual([row[0] for row in mod.list_pending_reviews(db,"mojplaywin")],[c])
        with self.assertRaises(RuntimeError):
            mod.save_reply(db,"zomorod",c,"Forged response from another tenant.","operator")
        self.assertEqual(db.execute("SELECT processing_status FROM customer_questions WHERE id=?",
                                    (c,)).fetchone()[0],"needs_review")
        db.close()

    def test_never_mutates_native_order_records(self):
        db=self.make_db()
        db.execute("CREATE TABLE native_order(id INTEGER PRIMARY KEY,status TEXT)")
        db.execute("INSERT INTO native_order VALUES(99,'paid')")
        ticket="f"*24
        db.execute("INSERT INTO customer_questions(id,tenant,processing_status,master_processed_utc) VALUES(?,?,?,?)",(ticket,"mojplaywin","needs_review",None))
        self.assertEqual(mod.save_reply(db,"mojplaywin",ticket,"We have your question and will respond.","operator"),"stored")
        self.assertEqual(db.execute("SELECT status FROM native_order WHERE id=99").fetchone()[0],"paid")
        db.close()


if __name__=="__main__":
    unittest.main()
