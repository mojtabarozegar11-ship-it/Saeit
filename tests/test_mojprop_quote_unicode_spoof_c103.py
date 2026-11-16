"""Regression for invisible Unicode contract-term spoofing (source-only)."""
import unittest
from core.mojprop_quote_contract import QuoteContractError, _text


class QuoteTextSecurityTests(unittest.TestCase):
    def test_hidden_formatting_rejected_in_every_contract_field(self):
        fields = (("title", 3, 180), ("scope", 50, 10000),
                  ("exclusions", 10, 5000))
        unsafe = ("\u202e", "\u202a", "\u2066", "\u2069",
                  "\u200b", "\u200d", "\ufeff", "\u2028", "\u2029")
        for field, minimum, maximum in fields:
            for character in unsafe:
                with self.subTest(field=field, codepoint=ord(character)):
                    value = "A" * minimum + character + "B"
                    with self.assertRaises(QuoteContractError):
                        _text(value, field, minimum, maximum)

    def test_normal_multilingual_scope_is_allowed(self):
        value = "شرح خدمات آموزشی مج پراپ با جزئیات روشن و قابل پیگیری"
        self.assertEqual(_text(value, "scope", 50, 10000), value)

    def test_scope_line_breaks_remain_supported(self):
        value = "Scope details for a written quote with multiple lines.\nExclusions documented."
        self.assertEqual(_text(value, "scope", 50, 10000), value)


if __name__ == "__main__":
    unittest.main()
