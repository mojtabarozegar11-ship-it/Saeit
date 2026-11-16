"""Regression: buyer acceptance audit references must remain visibly unambiguous."""
import unittest
from core.mojprop_quote_contract import QuoteContractError, validate_acceptance_reference


class AcceptanceReferenceUnicodeSafety(unittest.TestCase):
    def test_plain_reference_remains_valid(self):
        self.assertEqual(validate_acceptance_reference("CONSENT-20261116-ABC"), "CONSENT-20261116-ABC")

    def test_invisible_and_directional_unicode_rejected(self):
        for character in ("\u200b", "\u200c", "\u200d", "\u2060", "\ufeff",
                          "\u2028", "\u2029", "\u202e", "\u2066", "\u0000"):
            with self.subTest(character=repr(character)):
                with self.assertRaises(QuoteContractError):
                    validate_acceptance_reference("CONSENT-" + character + "20261116")


if __name__ == "__main__":
    unittest.main()
