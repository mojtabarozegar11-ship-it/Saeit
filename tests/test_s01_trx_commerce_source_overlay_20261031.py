"""S-01 synthetic contract and fail-closed checkout rate overlay tests.

No live commerce imports, DB connections, orders, payments or source writes.
"""
import ast
import sys
from types import ModuleType
from decimal import Decimal
import unittest
from unittest.mock import patch

from scripts import s01_trx_commerce_source_overlay_20261031 as overlay
from scripts.s01_trx_rate_isolation_candidate import (
    TrustedRateUnavailable, TrustedTrxRate,
)

BASE = '''def _rate_provider():
    from mpw_commerce.buyer_wallets import fetch_server_rate
    quote=fetch_server_rate("TRX")
    return quote.usd_per_asset, quote.observed_at

def unrelated(value):
    return value * 2
'''


class TrxCommerceOverlayTests(unittest.TestCase):
    @staticmethod
    def fake_rate_module(error_type):
        module = ModuleType("scripts.mojplaywin_direct_wallet_rates")
        module.RateFeedUnavailable = error_type
        return module

    def candidate(self, source=BASE):
        raw = source.encode("utf8")
        return overlay.build(raw, expected_sha256=overlay.digest(raw))

    def test_preserves_unrelated_source_and_tuple_contract(self):
        candidate = self.candidate()
        self.assertIn(b"from scripts.s01_trx_rate_isolation_candidate import", candidate)
        self.assertIn(b"def unrelated(value):\n    return value * 2", candidate)
        self.assertNotIn(b'fetch_server_rate("TRX")', candidate)
        # Original rate function no longer references any old global feed.
        fn = overlay._function(ast.parse(candidate))
        self.assertFalse(any(isinstance(n, ast.Name) and n.id == "fetch_server_rate"
                             for n in ast.walk(fn)))

    def test_fresh_trx_preserves_decimal_and_timestamp(self):
        revised = self.candidate().decode("utf8")
        class RateFeedUnavailable(Exception):
            pass
        scope = {"RateFeedUnavailable": RateFeedUnavailable}
        # Execute only the replaced function, not the original import or app.
        fn = overlay._function(ast.parse(revised))
        exec(compile(ast.Module(body=[fn], type_ignores=[]), "<synthetic>", "exec"), scope)
        observed = TrustedTrxRate(Decimal("0.285"), 1793470000, 30)
        with patch.dict(sys.modules, {"scripts.mojplaywin_direct_wallet_rates":
                                      self.fake_rate_module(RateFeedUnavailable)}), \
             patch("scripts.s01_trx_rate_isolation_candidate.fetch_trx_only", return_value=observed):
            amount, timestamp = scope["_rate_provider"]()
        self.assertEqual(amount, Decimal("0.285"))
        self.assertEqual(timestamp, 1793470000)

    def test_stale_trx_fails_with_existing_commerce_exception(self):
        revised = self.candidate().decode("utf8")
        class RateFeedUnavailable(Exception):
            pass
        scope = {"RateFeedUnavailable": RateFeedUnavailable}
        fn = overlay._function(ast.parse(revised))
        exec(compile(ast.Module(body=[fn], type_ignores=[]), "<synthetic>", "exec"), scope)
        with patch.dict(sys.modules, {"scripts.mojplaywin_direct_wallet_rates":
                                      self.fake_rate_module(RateFeedUnavailable)}), \
             patch("scripts.s01_trx_rate_isolation_candidate.fetch_trx_only",
                   side_effect=TrustedRateUnavailable("stale")):
            with self.assertRaises(RateFeedUnavailable):
                scope["_rate_provider"]()

    def test_unrealistic_quote_fails_closed(self):
        revised = self.candidate().decode("utf8")
        class RateFeedUnavailable(Exception):
            pass
        scope = {"RateFeedUnavailable": RateFeedUnavailable}
        fn = overlay._function(ast.parse(revised))
        exec(compile(ast.Module(body=[fn], type_ignores=[]), "<synthetic>", "exec"), scope)
        observed = TrustedTrxRate(Decimal("150"), 1793470000, 30)
        with patch.dict(sys.modules, {"scripts.mojplaywin_direct_wallet_rates":
                                      self.fake_rate_module(RateFeedUnavailable)}), \
             patch("scripts.s01_trx_rate_isolation_candidate.fetch_trx_only", return_value=observed):
            with self.assertRaises(RateFeedUnavailable):
                scope["_rate_provider"]()

    def test_source_drift_refused(self):
        with self.assertRaisesRegex(overlay.SourceContractChanged, "SHA drift"):
            overlay.build(BASE.encode("utf8"))

    def test_tuple_order_change_refused(self):
        changed = BASE.replace(
            "return quote.usd_per_asset, quote.observed_at",
            "return quote.observed_at, quote.usd_per_asset")
        with self.assertRaisesRegex(overlay.SourceContractChanged, "Return field"):
            self.candidate(changed)

    def test_extra_side_effect_refused(self):
        changed = BASE.replace('quote=fetch_server_rate("TRX")',
                               'print("unexpected")\n    quote=fetch_server_rate("TRX")')
        with self.assertRaisesRegex(overlay.SourceContractChanged, "body changed"):
            self.candidate(changed)

    def test_unrecognized_rate_error_contract_refused(self):
        changed = BASE.replace(
            "from mpw_commerce.buyer_wallets import fetch_server_rate",
            "from scripts.changed_rate_module import fetch_server_rate")
        with self.assertRaisesRegex(overlay.SourceContractChanged, "original import"):
            self.candidate(changed)

    def test_actual_source_ast_smoke_with_stubs(self):
        overlay.actual_source_in_memory_smoke(self.candidate())

    def test_no_install_mode_exists(self):
        self.assertFalse(hasattr(overlay, "install"))
        self.assertFalse(hasattr(overlay, "publish"))


if __name__ == "__main__":
    unittest.main()
