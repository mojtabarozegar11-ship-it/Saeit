"""Offline secure checkout behavior, no bank calls or real payment processing."""
import sqlite3
import unittest

from mpw_fiat_to_trx_20261020.guest_order_vault import (
    initialize, create_order, bind_invoice, status, GuestOrderError
)

class NoAccountFiatOrderTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        initialize(self.db)
        self.nonce = "request_nonce_" + "A" * 48
        self.clock = 1792550000

    def tearDown(self):
        self.db.close()

    def create(self, *, nonce=None, price="7.50", product=72):
        return create_order(
            self.db, product_id=product, price_usd=price,
            client_nonce=nonce or self.nonce, now=self.clock,
        )

    def test_initial_guest_order_is_private_and_unpaid(self):
        order = self.create()
        self.assertRegex(order["order_id"], r"^MPWF-[0-9a-f]{36}$")
        self.assertGreaterEqual(len(order["claim"]), 48)
        self.assertFalse(order["reused"])
        obj = status(self.db, order_id=order["order_id"],
                     claim=order["claim"], now=self.clock)
        self.assertEqual(obj["price_usd"], "7.50")
        self.assertEqual(obj["state"], "created")
        self.assertFalse(obj["has_invoice"])
        self.assertFalse(obj["safe_to_fulfill"])
        self.assertEqual(self.db.execute(
            "SELECT count(*) FROM fiat_guest_orders").fetchone()[0], 1)

    def test_idempotent_retry_does_not_issue_fresh_claim_or_order(self):
        first = self.create()
        second = self.create()
        self.assertTrue(second["reused"])
        self.assertIsNone(second["claim"])
        self.assertEqual(first["order_id"], second["order_id"])
        self.assertEqual(self.db.execute(
            "SELECT count(*) FROM fiat_guest_orders").fetchone()[0], 1)
        with self.assertRaises(GuestOrderError):
            self.create(price="4.00")
        with self.assertRaises(GuestOrderError):
            self.create(product=225)

    def test_guest_order_requires_strong_opaque_claim(self):
        o = self.create()
        for fake in ("x" * 72, o["claim"][:-1] + "*", "", None):
            with self.subTest(fake=fake), self.assertRaises(GuestOrderError):
                status(self.db, order_id=o["order_id"],
                       claim=fake, now=self.clock)
        with self.assertRaises(GuestOrderError):
            status(self.db, order_id="MPWF-UNRELATED", claim=o["claim"],
                   now=self.clock)

    def test_can_bind_verified_provider_url_once_without_entitlement(self):
        o = self.create()
        first = bind_invoice(self.db, order_id=o["order_id"],
                             claim=o["claim"], invoice_id=1234,
                             invoice_url="https://nowpayments.io/payment/1234",
                             now=self.clock+4)
        self.assertFalse(first["reused"])
        second = bind_invoice(self.db, order_id=o["order_id"],
                              claim=o["claim"], invoice_id="1234",
                              invoice_url="https://nowpayments.io/payment/1234",
                              now=self.clock+5)
        self.assertTrue(second["reused"])
        state = status(self.db, order_id=o["order_id"],
                       claim=o["claim"], now=self.clock+5)
        self.assertEqual(state["state"], "awaiting_payment")
        self.assertTrue(state["has_invoice"])
        self.assertFalse(state["safe_to_fulfill"])
        self.assertEqual(self.db.execute(
            "SELECT distinct state FROM fiat_guest_orders").fetchone()[0],
            "awaiting_payment")

    def test_never_rebinds_to_other_invoice_or_bad_host(self):
        o = self.create()
        bind_invoice(self.db, order_id=o["order_id"], claim=o["claim"],
                     invoice_id=1234, invoice_url="https://nowpayments.io/payment/1234",
                     now=self.clock)
        for change in (
            {"invoice_id": 1235, "invoice_url":"https://nowpayments.io/payment/1235"},
            {"invoice_id":1234,"invoice_url":"https://evil.invalid/phishing"},
        ):
            with self.subTest(**change), self.assertRaises(GuestOrderError):
                bind_invoice(self.db, order_id=o["order_id"], claim=o["claim"],
                             now=self.clock+1, **change)
        other=self.create(nonce="different_nonce_"+"B"*48)
        with self.assertRaises(GuestOrderError):
            bind_invoice(self.db, order_id=other["order_id"], claim=other["claim"],
                         invoice_id=1234, invoice_url="https://nowpayments.io/payment/1234",
                         now=self.clock+1)

    def test_expiry_and_cents_are_fail_closed(self):
        o=self.create()
        self.assertTrue(status(self.db, order_id=o["order_id"],
                               claim=o["claim"], now=self.clock+900)["expired"])
        with self.assertRaises(GuestOrderError):
            bind_invoice(self.db, order_id=o["order_id"], claim=o["claim"],
                         invoice_id=551, invoice_url="https://nowpayments.io/payment/551",
                         now=self.clock+900)
        for bad in ("0","-1","3.009","NaN","Infinity","1000.01",None,True):
            with self.subTest(bad=bad), self.assertRaises(GuestOrderError):
                self.create(nonce="invalid_nonce_"+"Q"*48,price=bad)
        with self.assertRaises(GuestOrderError):
            self.create(product=True)

    def test_sql_schema_cannot_mark_paid_or_refunded_without_real_verifier(self):
        o=self.create()
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute(
                "UPDATE fiat_guest_orders SET state='paid' WHERE order_id=?",
                (o["order_id"],)
            )
        self.db.rollback()
        state = status(self.db, order_id=o["order_id"],
                       claim=o["claim"], now=self.clock)
        self.assertFalse(state["safe_to_fulfill"])
        self.assertEqual(state["state"], "created")

if __name__ == "__main__":
    unittest.main()
