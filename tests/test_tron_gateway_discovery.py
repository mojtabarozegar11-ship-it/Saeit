"""Read-only deposit discovery tests. All API and chain calls are mocked."""
import copy
import time
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from core.tron_gateway_verify import MAINNET_RECEIVER, PaymentNotFinal, address_hex
from core.tron_gateway_discovery import native_candidate, receiver_candidates

TX = "a" * 64
SUN = 2100000
MIN = 1800000000000
MAX = MIN + 3600000


def fake_tx(txid=TX, sun=SUN, stamp=MIN+30000):
    return {
        "txID": txid,
        "block_timestamp": stamp,
        "raw_data": {
            "contract": [{
                "type": "TransferContract",
                "parameter": {"value": {
                    "owner_address": "41" + "c" * 40,
                    "to_address": address_hex(MAINNET_RECEIVER),
                    "amount": sun,
                }},
            }]
        },
    }


@override_settings(TRON_UNIFIED_TRONGRID_API_KEY="readonly-token-123456789")
class TronDiscoveryTests(SimpleTestCase):
    def test_native_incoming_tx_is_only_a_candidate(self):
        self.assertEqual(native_candidate(
            fake_tx(), recipient_hex=address_hex(MAINNET_RECEIVER)),
            (TX, SUN, MIN+30000))

    def test_token_contract_is_not_native_trx(self):
        row = fake_tx()
        row["raw_data"]["contract"][0]["type"] = "TriggerSmartContract"
        self.assertIsNone(native_candidate(
            row, recipient_hex=address_hex(MAINNET_RECEIVER)))

    def test_external_recipient_is_ignored(self):
        row = fake_tx()
        row["raw_data"]["contract"][0]["parameter"]["value"]["to_address"] = "41" + "e"*40
        self.assertIsNone(native_candidate(
            row, recipient_hex=address_hex(MAINNET_RECEIVER)))

    def test_wrong_amount_type_is_ignored(self):
        row = fake_tx()
        row["raw_data"]["contract"][0]["parameter"]["value"]["amount"] = True
        self.assertIsNone(native_candidate(
            row, recipient_hex=address_hex(MAINNET_RECEIVER)))

    def test_invalid_tx_body_is_ignored(self):
        row = fake_tx()
        row["raw_data"] = ["bad-data"]
        self.assertIsNone(native_candidate(
            row, recipient_hex=address_hex(MAINNET_RECEIVER)))

    def test_duplicate_candidates_across_index_pages_are_deduplicated(self):
        requests = []
        def fetch(params, *, api_key):
            requests.append(copy.deepcopy(params))
            if len(requests) == 1:
                return {"success": True, "data": [fake_tx()],
                        "meta": {"fingerprint": "page2"}}
            return {"success": True, "data": [fake_tx()], "meta": {}}
        rows, truncated = receiver_candidates(
            min_ms=MIN, max_ms=MAX, fetch=fetch)
        self.assertEqual(len(rows), 1)
        self.assertFalse(truncated)
        self.assertEqual(requests[1]["fingerprint"], "page2")

    def test_pagination_beyond_bounded_pages_is_reported_not_concealed(self):
        def fetch(params, *, api_key):
            return {"success": True, "data": [fake_tx()],
                    "meta": {"fingerprint": "page-" + str(params.get("fingerprint", "1"))}}
        rows, truncated = receiver_candidates(
            min_ms=MIN, max_ms=MAX, pages=2, fetch=fetch)
        self.assertEqual(len(rows), 1)
        self.assertTrue(truncated)

    def test_malformed_pagination_is_rejected(self):
        def fetch(params, *, api_key):
            return {"success": True, "data": [fake_tx()],
                    "meta": {"fingerprint": "/evil?query=1&host=internal"}}
        with self.assertRaises(PaymentNotFinal):
            receiver_candidates(min_ms=MIN, max_ms=MAX, fetch=fetch)

    def test_reused_fingerprint_is_rejected(self):
        def fetch(params, *, api_key):
            return {"success": True, "data": [fake_tx()],
                    "meta": {"fingerprint": "samepage"}}
        with self.assertRaises(PaymentNotFinal):
            receiver_candidates(min_ms=MIN, max_ms=MAX, fetch=fetch)

    @override_settings(TRON_UNIFIED_TRONGRID_API_KEY="")
    def test_missing_secret_disables_discovery(self):
        with self.assertRaises(PaymentNotFinal):
            receiver_candidates(min_ms=MIN, max_ms=MAX,
                                fetch=lambda *a, **kw: None)

    def test_bad_time_window_fails_before_network(self):
        with self.assertRaises(PaymentNotFinal):
            receiver_candidates(min_ms=MAX, max_ms=MIN,
                                fetch=lambda *a, **kw: None)
