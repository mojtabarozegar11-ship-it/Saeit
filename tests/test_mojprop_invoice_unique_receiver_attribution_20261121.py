"""No real TRX, email, network activity, or production database mutation.

The only safe automated credit is one blockchain receiver permanently owned by
one verified invoice; a public txid or unsigned sender address is not enough.
"""
from __future__ import annotations

import inspect
import json
from unittest.mock import patch

from django.test import SimpleTestCase

from prop_firm import starter30_receiver_pool as pool
from prop_firm.models import PropSimulationPayment
from prop_firm import starter30_live


class InvoiceReceiverAttributionTests(SimpleTestCase):
    A = "T" + "A" * 33
    B = "T" + "B" * 33
    SHARED = "T" + "S" * 33
    EVIDENCE = "offline-wallet-control-20261121"

    def setUp(self):
        self.v = patch.object(pool, "validate_tron_recipient")
        self.v.start()
        self.addCleanup(self.v.stop)
        self.o = patch.object(pool, "approved_recipient", return_value=self.SHARED)
        self.o.start()
        self.addCleanup(self.o.stop)

    def config(self, addresses=None, **overrides):
        values = {
            "MPW_MOJPROP_INVOICE_ADDRESS_POOL_VERIFIED": True,
            "MPW_MOJPROP_INVOICE_ADDRESS_POOL_JSON": json.dumps(
                [self.A, self.B] if addresses is None else addresses
            ),
            "MPW_MOJPROP_INVOICE_ADDRESS_CONTROL_REF": self.EVIDENCE,
        }
        values.update(overrides)
        return self.settings(**values)

    def test_default_closed_even_with_addresses(self):
        with self.config(MPW_MOJPROP_INVOICE_ADDRESS_POOL_VERIFIED=False):
            with self.assertRaises(pool.InvoiceAttributionUnavailable):
                pool.attested_receivers()

    def test_numeric_truthy_cannot_unlock(self):
        with self.config(MPW_MOJPROP_INVOICE_ADDRESS_POOL_VERIFIED=1):
            with self.assertRaises(pool.InvoiceAttributionUnavailable):
                pool.attested_receivers()

    def test_missing_control_proof(self):
        with self.config(MPW_MOJPROP_INVOICE_ADDRESS_CONTROL_REF=""):
            with self.assertRaises(pool.InvoiceAttributionUnavailable):
                pool.attested_receivers()

    def test_valid_returns_immutable_unique_pool(self):
        with self.config():
            self.assertEqual(pool.attested_receivers(), (self.A, self.B))

    def test_reject_shared_store_wallet(self):
        with self.config([self.A, self.SHARED]):
            with self.assertRaises(pool.InvoiceAttributionUnavailable):
                pool.attested_receivers()

    def test_reject_duplicate_invoices_receiver(self):
        with self.config([self.A, self.A]):
            with self.assertRaises(pool.InvoiceAttributionUnavailable):
                pool.attested_receivers()

    def test_reject_missing_and_invalid_json(self):
        for raw in ("", "{", "null", '"not an array"', "[]"):
            with self.subTest(raw=raw), self.config(MPW_MOJPROP_INVOICE_ADDRESS_POOL_JSON=raw):
                with self.assertRaises(pool.InvoiceAttributionUnavailable):
                    pool.attested_receivers()

    def test_reject_overlong_pool(self):
        with self.config([self.A] * 257):
            with self.assertRaises(pool.InvoiceAttributionUnavailable):
                pool.attested_receivers()

    def test_reject_private_key_like_nonaddresses(self):
        for address in ("private_key", "xprv-secret", "T" + "x" * 34):
            with self.subTest(address=address), self.config([address]):
                with self.assertRaises(pool.InvoiceAttributionUnavailable):
                    pool.attested_receivers()

    def test_reject_invalid_checksum(self):
        with self.config():
            with patch.object(pool, "validate_tron_recipient", side_effect=ValueError("checksum")):
                with self.assertRaises(pool.InvoiceAttributionUnavailable):
                    pool.attested_receivers()

    def test_pick_next_unused_not_recycled(self):
        with self.config():
            addresses = pool.attested_receivers()
            self.assertEqual(pool.select_unused_receiver(addresses, set()), self.A)
            self.assertEqual(pool.select_unused_receiver(addresses, {self.A}), self.B)
            with self.assertRaises(pool.InvoiceAttributionUnavailable):
                pool.select_unused_receiver(addresses, {self.A, self.B})

    def test_reject_untrusted_allocation_types(self):
        with self.assertRaises(pool.InvoiceAttributionUnavailable):
            pool.select_unused_receiver([self.A], set())

    def test_verify_exact_unique_invoice_address(self):
        with self.config():
            self.assertIsNone(pool.require_payment_binding(
                recorded_recipient=self.A, onchain_recipient=self.A
            ))

    def test_public_txid_cannot_credit_other_invoice(self):
        with self.config():
            with self.assertRaises(pool.InvoiceAttributionUnavailable):
                pool.require_payment_binding(
                    recorded_recipient=self.A, onchain_recipient=self.B
                )

    def test_fake_old_shared_recipient_cannot_be_auto_credited(self):
        with self.config():
            with self.assertRaises(pool.InvoiceAttributionUnavailable):
                pool.require_payment_binding(
                    recorded_recipient=self.SHARED, onchain_recipient=self.SHARED
                )

    def test_database_schema_enforces_one_receiver_for_all_time(self):
        self.assertIs(PropSimulationPayment._meta.get_field("recipient").unique, True)
        self.assertIs(PropSimulationPayment._meta.get_field("txid").unique, True)

    def test_live_issue_path_uses_unique_receiver_atomically(self):
        source = inspect.getsource(starter30_live.issue_invoice)
        self.assertIn("transaction.atomic(using=MOJPROP_DB_ALIAS)", source)
        self.assertIn("select_unused_receiver(receivers, used)", source)
        self.assertIn("recipient=recipient", source)
        self.assertIn("except IntegrityError", source)
        self.assertNotIn("recipient=approved_recipient()", source)

    def test_live_settlement_requires_onchain_invoice_binding(self):
        source = inspect.getsource(starter30_live._settle_verified_invoice)
        self.assertIn("require_payment_binding(", source)
        self.assertIn("onchain_recipient=transfer_a.recipient", source)
        self.assertLess(source.index("require_payment_binding("), source.index("owner.settlement_verified = True"))

    def test_preinvoice_checks_pool_before_any_invoice(self):
        source = inspect.getsource(starter30_live.verify_pre_invoice_configuration)
        self.assertIn("attested_receivers()", source)
