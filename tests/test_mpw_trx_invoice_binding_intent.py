"""Contract tests for the persisted walletless TRON invoice envelope."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import json
from types import SimpleNamespace
import unittest

from services.mpw_trx_walletless_core import InvoiceIntent, PaymentHold
from services.mpw_walletless_commercial_intent import (
    PROVIDER,
    _decode,
    _encode,
)


RECEIVER = "T" + "A" * 33
ISSUED = datetime(2026, 11, 15, 12, 0, tzinfo=timezone.utc)


class InvoiceEnvelopeTests(unittest.TestCase):
    def _invoice(self, **overrides):
        values = {
            "order_id": 17,
            "customer_id": 23,
            "network": "tron-mainnet",
            "recipient": RECEIVER,
            "amount_sun": 1_234_567,
            "usd_total": Decimal("12.50"),
            "issued_at": ISSUED,
            "expires_at": datetime(2026, 11, 15, 12, 10, tzinfo=timezone.utc),
            "quote_usd_per_trx": Decimal("0.010"),
            "merchant_domain": "mojplaywin.com",
            "merchant_id": "mojplaywin-store",
        }
        values.update(overrides)
        return InvoiceIntent(**values)

    def test_encoded_envelope_contains_v2_merchant_identity(self):
        encoded = _encode(self._invoice())
        doc = json.loads(encoded)
        self.assertEqual(doc["v"], 2)
        self.assertEqual(doc["d"], "mojplaywin.com")
        self.assertEqual(doc["m"], "mojplaywin-store")
        self.assertLessEqual(len(encoded), 200)

    def test_decode_round_trip_preserves_identity(self):
        encoded = _encode(self._invoice())
        intent = SimpleNamespace(
            provider=PROVIDER,
            provider_reference=encoded,
            idempotency_key="wltrx1:"
            + __import__("hashlib").sha256(RECEIVER.encode("ascii")).hexdigest()
            + ":1234567",
            currency="USD",
            amount=Decimal("12.50"),
            order_id=17,
            order=SimpleNamespace(customer_id=23),
        )
        decoded = _decode(intent)
        self.assertEqual(decoded.merchant_domain, "mojplaywin.com")
        self.assertEqual(decoded.merchant_id, "mojplaywin-store")
        self.assertEqual(decoded.amount_sun, 1_234_567)

    def test_unbound_intent_never_becomes_payable_envelope(self):
        with self.assertRaises(PaymentHold):
            _encode(self._invoice(merchant_domain="", merchant_id=""))

    def test_v1_or_missing_fields_are_rejected(self):
        encoded = _encode(self._invoice())
        doc = json.loads(encoded)
        doc["v"] = 1
        doc.pop("d")
        doc.pop("m")
        intent = SimpleNamespace(
            provider=PROVIDER,
            provider_reference=json.dumps(doc),
            idempotency_key="wltrx1:"
            + __import__("hashlib").sha256(RECEIVER.encode("ascii")).hexdigest()
            + ":1234567",
            currency="USD",
            amount=Decimal("12.50"),
            order_id=17,
            order=SimpleNamespace(customer_id=23),
        )
        with self.assertRaises(PaymentHold):
            _decode(intent)


if __name__ == "__main__":
    unittest.main()
