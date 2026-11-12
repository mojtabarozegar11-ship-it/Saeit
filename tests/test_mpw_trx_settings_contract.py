"""Offline regression checks for explicit TRX public-sale configuration.

Parses and executes only the isolated settings declarations; no Django,
network, private checkout, secrets or money movements.
"""
from __future__ import annotations

import ast
import unittest
from pathlib import Path


SOURCE = Path(__file__).resolve().parents[1] / "config/settings.py"
BEGIN = "MPW_WALLETLESS_TRX_PUBLIC_ENABLED = env.bool("
END = "MPW_GUEST_RECOVERY_ENABLED = env.bool("


def settings_for(*, enabled=False, skus=None):
    data = SOURCE.read_text(encoding="utf-8")
    start = data.index(BEGIN)
    end = data.index(END, start)
    source = data[start:end]
    tree = ast.parse(source)
    class StubEnv:
        def bool(self, key, default=False):
            if key != "MPW_WALLETLESS_TRX_PUBLIC_ENABLED":
                raise AssertionError(key)
            return enabled
        def list(self, key, default=None):
            if key != "MPW_TRX_PUBLIC_PRODUCT_IDS":
                raise AssertionError(key)
            return list(default if skus is None else skus)
    data = {"env": StubEnv()}
    exec(compile(tree, str(SOURCE), "exec"), data)
    return data


class MPWTrxSettingsContractTests(unittest.TestCase):
    def test_default_is_three_flagship_products_but_public_payment_off(self):
        config = settings_for()
        self.assertEqual(config["MPW_TRX_PUBLIC_PRODUCT_IDS"], (72, 225, 879))
        self.assertFalse(config["MPW_WALLETLESS_TRX_PUBLIC_ENABLED"])
        self.assertTrue(config["MPW_TRX_PUBLIC_SKU_CONFIG_VALID"])

    def test_explicit_activation_is_separate_from_allowlist(self):
        config = settings_for(enabled=True, skus=["72", "225", "879", "991"])
        self.assertTrue(config["MPW_WALLETLESS_TRX_PUBLIC_ENABLED"])
        self.assertEqual(
            config["MPW_TRX_PUBLIC_PRODUCT_IDS"], (72, 225, 879, 991)
        )

    def test_explicitly_empty_list_disables_all_skus(self):
        config = settings_for(enabled=True, skus=[])
        self.assertEqual(config["MPW_TRX_PUBLIC_PRODUCT_IDS"], ())
        self.assertTrue(config["MPW_TRX_PUBLIC_SKU_CONFIG_VALID"])

    def test_invalid_configuration_fails_closed_without_crashing_site(self):
        for tokens in (
            ["72", "0"], ["72", "-1"], ["72", "abc"],
            ["72", "225;879"], ["72", "72"], ["72", "072"],
            ["72", "2147483648"],
        ):
            with self.subTest(tokens=tokens):
                config = settings_for(enabled=True, skus=tokens)
                self.assertEqual(config["MPW_TRX_PUBLIC_PRODUCT_IDS"], ())
                self.assertFalse(config["MPW_TRX_PUBLIC_SKU_CONFIG_VALID"])


if __name__ == "__main__":
    unittest.main()
