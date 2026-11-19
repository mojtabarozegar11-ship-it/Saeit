"""Regression coverage for native TRON wire evidence (no network or funds)."""
import copy
import hashlib
from datetime import datetime, timezone
from types import SimpleNamespace

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase
from prop_firm.simulation_tron_reconcile import recipient_hex, verify_invoice_transaction


def vint(number):
    data = bytearray()
    while number >= 128:
        data.append((number & 127) | 128)
        number >>= 7
    data.append(number)
    return bytes(data)


def num(field, value):
    return vint(field << 3) + vint(value)


def blob(field, value):
    return vint((field << 3) | 2) + vint(len(value)) + value


class SimulationNativeTronTests(SimpleTestCase):
    def setUp(self):
        self.invoice = SimpleNamespace(
            recipient="T9yD14Nj9j7xAB4dbGeiX9h8unkKHxuWwb",
            amount_sun=30_000_000, order_ref="SIM-012",
            created_at=datetime(2026, 11, 19, tzinfo=timezone.utc),
        )
        self.owner = bytes.fromhex("41" + "11" * 20)
        self.recipient = bytes.fromhex(recipient_hex(self.invoice.recipient))
        self.timestamp = int(self.invoice.created_at.timestamp() * 1000) + 1000

    def fixture(self, amount=30_000_000, memo=b"SIM-012", recipient=None, extra=b""):
        recipient = self.recipient if recipient is None else recipient
        transfer = blob(1, self.owner) + blob(2, recipient) + num(3, amount)
        any_value = blob(1, b"type.googleapis.com/protocol.TransferContract") + blob(2, transfer)
        contract = num(1, 1) + blob(2, any_value)
        raw = blob(10, memo) + blob(11, contract) + num(14, self.timestamp) + extra
        txid = hashlib.sha256(raw).hexdigest()
        body = {
            "txID": txid, "raw_data_hex": raw.hex(),
            "ret": [{"contractRet": "SUCCESS"}],
            "raw_data": {"data": b"SIM-012".hex(), "timestamp": self.timestamp,
                         "contract": [{"type": "TransferContract", "parameter": {"value": {
                             "owner_address": self.owner.hex(), "to_address": self.recipient.hex(),
                             "amount": 30_000_000}}}]}
        }
        return txid, body

    def test_matching_native_transfer_and_stable_digest(self):
        txid, body = self.fixture()
        digest = verify_invoice_transaction(self.invoice, txid, body)
        altered = copy.deepcopy(body)
        altered["provider_metadata"] = {"unrelated": True}
        self.assertEqual(digest, verify_invoice_transaction(self.invoice, txid, altered))
        self.assertEqual(len(digest), 64)

    def test_raw_amount_disagrees_with_json(self):
        txid, body = self.fixture(amount=1)
        with self.assertRaises(ValidationError):
            verify_invoice_transaction(self.invoice, txid, body)

    def test_raw_recipient_disagrees_with_json(self):
        txid, body = self.fixture(recipient=bytes.fromhex("41" + "22"*20))
        with self.assertRaises(ValidationError):
            verify_invoice_transaction(self.invoice, txid, body)

    def test_raw_memo_disagrees_with_json(self):
        txid, body = self.fixture(memo=b"SIM-OTHER")
        with self.assertRaises(ValidationError):
            verify_invoice_transaction(self.invoice, txid, body)

    def test_duplicate_timestamp_is_rejected(self):
        txid, body = self.fixture(extra=num(14, self.timestamp))
        with self.assertRaises(ValidationError):
            verify_invoice_transaction(self.invoice, txid, body)

    def test_forged_decoded_timestamp_is_rejected(self):
        txid, body = self.fixture()
        body["raw_data"]["timestamp"] += 1
        with self.assertRaises(ValidationError):
            verify_invoice_transaction(self.invoice, txid, body)

    def test_non_success_is_rejected(self):
        txid, body = self.fixture()
        body["ret"][0]["contractRet"] = "REVERT"
        with self.assertRaises(ValidationError):
            verify_invoice_transaction(self.invoice, txid, body)
