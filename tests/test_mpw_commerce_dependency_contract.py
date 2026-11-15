"""Pure tests for the restored MojPlayWin commerce dependencies."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import unittest

from scripts.mojplaywin_direct_wallet_rates import fetch_fresh_rates
from scripts.mojplaywin_native_chain_verify import VerificationError, tron_address_to_hex
from scripts.mpw_tron_public_dual_probe_readonly_20261023 import (
    NODES,
    head_height_and_age,
)


RECEIVER = "THFNU1iEXHd71WjEgjqUksd2UnMg2pUi73"


class CommerceDependencyTests(unittest.TestCase):
    def test_approved_receiver_is_validated_without_network(self):
        encoded = tron_address_to_hex(RECEIVER)
        self.assertEqual(len(encoded), 42)
        self.assertTrue(encoded.startswith("41"))

    def test_bad_receiver_checksum_is_rejected(self):
        with self.assertRaises(VerificationError):
            tron_address_to_hex(RECEIVER[:-1] + "4")

    def test_rate_adapter_accepts_only_injected_readonly_snapshot(self):
        now = datetime(2026, 11, 15, 13, 0, tzinfo=timezone.utc)
        result = fetch_fresh_rates(
            now=now,
            transport=lambda _url: (
                b'{"tron":{"usd":0.10},"ethereum":{"usd":2000.00}}'
            ),
        )
        self.assertEqual(result["TRX"].provider, "coingecko")
        self.assertEqual(result["TRX"].usd_per_asset, Decimal("0.10"))
        self.assertEqual(result["TRX"].observed_at_epoch, int(now.timestamp()))

    def test_tron_head_is_bounded_and_fresh(self):
        now = datetime.now(timezone.utc)
        block = {
            "block_header": {
                "raw_data": {
                    "number": 123456,
                    "timestamp": int(now.timestamp() * 1000),
                }
            }
        }
        self.assertEqual(head_height_and_age(block, now), 123456)

    def test_stale_head_fails_closed(self):
        now = datetime.now(timezone.utc)
        block = {
            "block_header": {
                "raw_data": {
                    "number": 123456,
                    "timestamp": int((now - timedelta(minutes=5)).timestamp() * 1000),
                }
            }
        }
        with self.assertRaises(ValueError):
            head_height_and_age(block, now)

    def test_provider_pair_is_fixed_and_read_only(self):
        self.assertEqual(
            NODES,
            (
                ("publicnode-allnodes", "https://tron-solidity-rpc.publicnode.com"),
                ("trongrid", "https://api.trongrid.io"),
            ),
        )


if __name__ == "__main__":
    unittest.main()
