"""Portable adversarial native-TRX buyer email policy regressions, no Django/RPC."""
import unittest
from core.tron_gateway_identity import normalize_buyer_email


def fake_validator(email):
    if email.count("@") != 1 or not email.split("@")[-1].count("."):
        raise ValueError("Invalid email syntax")


class BuyerEmailPolicyTests(unittest.TestCase):
    def check_bad(self, value):
        with self.assertRaises(ValueError):
            normalize_buyer_email(value, fake_validator)

    def test_plain_email(self):
        self.assertEqual(normalize_buyer_email("buyer@example.com", fake_validator), "buyer@example.com")

    def test_mixed_case_email_canonicalized(self):
        self.assertEqual(normalize_buyer_email("BUYER@Example.COM", fake_validator), "buyer@example.com")

    def test_surrounding_printable_spaces_allowed(self):
        self.assertEqual(normalize_buyer_email("  buyer@example.com  ", fake_validator), "buyer@example.com")

    def test_leading_newline_rejected(self):
        self.check_bad("\nbuyer@example.com")

    def test_trailing_newline_rejected(self):
        self.check_bad("buyer@example.com\n")

    def test_trailing_carriage_return_rejected(self):
        self.check_bad("buyer@example.com\r")

    def test_tab_rejected(self):
        self.check_bad("buyer@\texample.com")

    def test_null_byte_rejected(self):
        self.check_bad("buyer@example.com\0")

    def test_del_character_rejected(self):
        self.check_bad("buyer@example.com\x7f")

    def test_c1_control_rejected(self):
        self.check_bad("buyer@example.com\x85")

    def test_zero_width_character_rejected(self):
        self.check_bad("buyer@exa\u200bmple.com")

    def test_direction_override_rejected(self):
        self.check_bad("buyer@exa\u202emple.com")

    def test_surrogate_rejected(self):
        self.check_bad("buyer@example.com\ud800")

    def test_short_email_rejected(self):
        self.check_bad("a@b.c")

    def test_oversize_email_rejected(self):
        self.check_bad("a" * 255 + "@example.com")

    def test_invalid_missing_at_rejected_by_validator(self):
        self.check_bad("buyer.example.com")

    def test_boolean_not_accepted(self):
        self.check_bad(True)

    def test_bytes_not_accepted(self):
        self.check_bad(b"buyer@example.com")

    def test_none_not_accepted(self):
        self.check_bad(None)

    def test_validator_invoked_once_on_canonical_email(self):
        values = []
        result = normalize_buyer_email("  USER@Example.COM ", values.append)
        self.assertEqual(result, "user@example.com")
        self.assertEqual(values, ["user@example.com"])

    def test_no_validator_called_for_control_input(self):
        values = []
        self.check_bad("buyer@example.com\n")
        with self.assertRaises(ValueError):
            normalize_buyer_email("buyer@example.com\n", values.append)
        self.assertEqual(values, [])

    def test_validator_error_is_not_concealed(self):
        def reject(_email):
            raise ValueError("rejected by strict validator")
        with self.assertRaisesRegex(ValueError, "strict validator"):
            normalize_buyer_email("buyer@example.com", reject)

    def test_idempotence(self):
        first = normalize_buyer_email("  BUYER@EXAMPLE.COM ", fake_validator)
        self.assertEqual(normalize_buyer_email(first, fake_validator), first)

    def test_international_email_passes_to_validator_without_transliteration(self):
        email = "کاربر@مثال.ایران"
        self.assertEqual(normalize_buyer_email(email, fake_validator), email)


if __name__ == "__main__":
    unittest.main()
