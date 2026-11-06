"""Offline contract: refunded TRX receipts cannot authorize paid downloads."""
from __future__ import annotations

import ast
from datetime import datetime
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import re
from types import SimpleNamespace
import unittest


SOURCE = Path(__file__).resolve().parents[1] / "core/crown_tron_receipts.py"
PROVIDER = "mpw_walletless_trx_v1"
TX_HASH = re.compile(r"[0-9a-f]{64}\Z")
TRON_ADDRESS = re.compile(r"T[1-9A-HJ-NP-Za-km-z]{33}\Z")


class Query:
    def __init__(self, rows):
        self.rows = rows

    def __getitem__(self, key):
        return self.rows[key]

    def exists(self):
        return bool(self.rows)


class RefundVeto(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tree = ast.parse(SOURCE.read_text("utf-8"))
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                    and n.name == "verified_walletless_credit")
        cls.code = compile(ast.Module(body=[node], type_ignores=[]), str(SOURCE), "exec")

    def receipt(self, reversal_type=None):
        receiver = "T" + "A" * 33
        tx = "a" * 64
        evidence = "b" * 64
        order = SimpleNamespace(pk=19, status="paid", total=Decimal("4.99"), currency="USD")
        envelope = {"v": 1, "to": receiver, "sun": 19960000, "rate": "0.25",
                    "at": "2026-10-22T08:00:00+00:00"}
        intent = SimpleNamespace(
            provider=PROVIDER, status="paid", order_id=order.pk,
            currency="USD", amount=order.total,
            provider_reference=json.dumps(envelope),
            idempotency_key="wltrx1:" + hashlib.sha256(receiver.encode()).hexdigest() + ":19960000",
        )
        event = SimpleNamespace(pk=11, event_id=tx, payload_hash=evidence)
        credit = SimpleNamespace(
            amount=order.total, currency="USD", reference="walletless:tron-mainnet:" + tx,
            metadata={"payment_method": PROVIDER, "network": "tron-mainnet", "tx_hash": tx,
                      "evidence_digest": evidence, "walletless_receipt_event_id": 11,
                      "sender": "T" + "B" * 33},
        )
        refund = ([SimpleNamespace(entry_type=reversal_type, payment_intent=None)]
                  if reversal_type else [])

        class Ledger:
            def filter(self, **where):
                if "entry_type__in" in where:
                    self_check = where["entry_type__in"]
                    assert set(self_check) == {"refund", "reversal", "chargeback"}
                    assert where["order"] is order
                    return Query(refund)
                assert where == {"order": order, "payment_intent": intent,
                                 "entry_type": "credit"}
                return Query([credit])

        class Events:
            def filter(self, **where):
                assert where == {"payment_intent": intent, "provider": PROVIDER,
                                 "event_type": "tron_finalized", "status": "processed"}
                return Query([event])

        values = {
            "PROVIDER": PROVIDER, "NETWORK": "tron-mainnet", "TX_HASH": TX_HASH,
            "TRON_ADDRESS": TRON_ADDRESS, "LedgerEntry": SimpleNamespace(objects=Ledger()),
            "PaymentWebhookEvent": SimpleNamespace(objects=Events()),
            "Decimal": Decimal, "InvalidOperation": InvalidOperation,
            "datetime": datetime, "hashlib": hashlib, "json": json,
        }
        exec(self.code, values)
        return values["verified_walletless_credit"](order, intent)

    def test_valid_solidified_receipt_remains_accepted(self):
        self.assertTrue(self.receipt())

    def test_order_level_refund_reversal_and_chargeback_block_entitlement(self):
        for kind in ("refund", "reversal", "chargeback"):
            with self.subTest(kind=kind):
                self.assertFalse(self.receipt(reversal_type=kind))


if __name__ == "__main__":
    unittest.main()
