"""No-host, no-payment contracts for exact-anchor TRX patch preview."""
import unittest
from scripts.mpw_trx_live_patchability_readonly_20261101 import classify_current, _transform


def fixtures():
    buyer = (
        "def fetch_server_rate(asset):\n"
        "    snap=fetch_fresh_rates()\n"
        "    return snap[asset]\n"
    )
    rates = (
        "def parse_coin_gecko_rates(document, now_epoch):\n"
        "    result = {}\n"
        "    for symbol, coin_id in ((\"ETH\", \"ethereum\"), (\"TRX\", \"tron\")):\n"
        "        result[symbol] = document.get(coin_id)\n"
        "    return result\n"
        "\n"
        "def fetch_fresh_rates(*, fetch=urlopen, now=None):\n"
        "    return parse_coin_gecko_rates(doc, now)\n"
    )
    return {"buyer": buyer.encode(), "rate": rates.encode()}


class PatchPreviewTests(unittest.TestCase):
    def test_narrow_quote_patch_preserves_code_and_never_writes(self):
        result = classify_current(fixtures())
        self.assertTrue(result["buyer_patchable"])
        self.assertTrue(result["rate_patchable"])
        self.assertTrue(result["buyer_pins_requested_asset"])
        self.assertTrue(result["rate_functions_keep_existing_names"])
        self.assertTrue(result["rate_quote_accepts_requested_assets"])
        self.assertFalse(result["release_permitted"])
        self.assertFalse(result["db_accessed"])
        self.assertFalse(result["source_changed"])
        self.assertFalse(result["payments_created"])

    def test_changed_buyer_anchor_fails_closed(self):
        sources = fixtures()
        sources["buyer"] = sources["buyer"].replace(
            b"snap=fetch_fresh_rates()", b"snap=fetch_cached_rate()")
        with self.assertRaisesRegex(ValueError, "Unexpected source anchor"):
            classify_current(sources)

    def test_duplicate_rate_anchor_fails_closed(self):
        sources = fixtures()
        sources["rate"] += b"\ndef parse_coin_gecko_rates(document, now_epoch):\n    pass\n"
        with self.assertRaisesRegex(ValueError, "Unexpected source anchor"):
            classify_current(sources)


if __name__ == "__main__":
    unittest.main()
