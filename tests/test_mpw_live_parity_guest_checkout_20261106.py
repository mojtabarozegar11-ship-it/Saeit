"""Regression contracts for MojPlayWin live-parity guest checkout fixes.

These tests are source-only: they create no orders, payments, emails or database rows.
"""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
GUEST = (ROOT / "services/mpw_trx_guest_commerce.py").read_text("utf-8")


class GuestLiveParityContracts(unittest.TestCase):
    def test_new_guest_explicitly_clears_privileged_flags(self):
        self.assertIn('for privileged_flag in ("is_staff", "is_superuser"):', GUEST)
        self.assertIn('setattr(user, privileged_flag, False)', GUEST)
        self.assertIn('getattr(user, "is_staff", False)', GUEST)
        self.assertIn('getattr(user, "is_superuser", False)', GUEST)

    def test_existing_guest_binding_does_not_require_username_attribute(self):
        self.assertIn('elif user is not None and create:', GUEST)
        self.assertNotIn(
            'and str(getattr(user, "username", "")).startswith("mpwguest_")',
            GUEST,
        )

    def test_only_an_invoice_redirect_counts_as_accepted_checkout(self):
        self.assertIn("def _is_invoice_redirect(response):", GUEST)
        self.assertIn('getattr(response, "status_code", None) in (302, 303)', GUEST)
        self.assertIn("INVOICE_LOCATION.fullmatch(location) is not None", GUEST)
        self.assertNotIn(
            'if create and 200 <= getattr(response, "status_code", 500) < 400:',
            GUEST,
        )

    def test_email_aliases_are_collected_with_getlist_and_conflicts_rejected(self):
        self.assertGreaterEqual(GUEST.count("request.POST.getlist(key)"), 1)
        self.assertIn(
            "any(value != values[0] for value in values)",
            GUEST,
        )


if __name__ == "__main__":
    unittest.main()
