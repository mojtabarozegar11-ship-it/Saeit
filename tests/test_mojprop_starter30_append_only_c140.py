"""C140: execute actual Django model.save() append-only guards, without DB writes.

These are model-unit tests, not proof that raw SQL or QuerySet.update() cannot
mutate a production row. DB permissions, isolated MariaDB restore, merchant
authority and independent replay-safe payment ledger remain release blockers.
"""
import unittest
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import models

from core.models import MojPropStarter30Order, MojPropStarter30TxClaim


class Starter30AppendOnlyORMTests(unittest.TestCase):
    def _denied(self, instance, *, kw=None):
        # The refusal must occur BEFORE validation or any database write.
        with patch.object(instance, "full_clean") as validated:
            with patch.object(models.Model, "save", side_effect=AssertionError("DB write attempted")) as write:
                with self.assertRaises(ValidationError):
                    instance.save(**(kw or {}))
            validated.assert_not_called()
            write.assert_not_called()

    def _fresh_insert_path(self, instance):
        self.assertIsNone(instance.pk)
        self.assertTrue(instance._state.adding)
        with patch.object(instance, "full_clean") as validated:
            with patch.object(models.Model, "save", return_value="NO_DB_WRITE") as write:
                self.assertEqual(instance.save(force_insert=True), "NO_DB_WRITE")
        validated.assert_called_once()
        write.assert_called_once()

    def test_01_new_order_uses_existing_validation_and_insert_path(self):
        self._fresh_insert_path(MojPropStarter30Order())

    def test_02_new_claim_uses_existing_validation_and_insert_path(self):
        self._fresh_insert_path(MojPropStarter30TxClaim())

    def test_03_existing_order_pk_cannot_be_resaved(self):
        self._denied(MojPropStarter30Order(id=51))

    def test_04_existing_claim_pk_cannot_be_resaved(self):
        self._denied(MojPropStarter30TxClaim(id=52))

    def test_05_existing_order_force_insert_cannot_overwrite(self):
        self._denied(MojPropStarter30Order(id=53), kw={"force_insert": True})

    def test_06_existing_claim_force_insert_cannot_overwrite(self):
        self._denied(MojPropStarter30TxClaim(id=54), kw={"force_insert": True})

    def test_07_saved_order_update_fields_cannot_rebind_payer(self):
        order = MojPropStarter30Order(id=55, payer_hex41="41" + "a" * 40)
        self._denied(order, kw={"update_fields": ["payer_hex41"]})

    def test_08_saved_order_update_fields_cannot_rebind_receiver(self):
        order = MojPropStarter30Order(id=56, recipient="T" + "a" * 33)
        self._denied(order, kw={"update_fields": ["recipient"]})

    def test_09_saved_order_update_fields_cannot_rewrite_terms(self):
        order = MojPropStarter30Order(id=57, buyer_terms_acceptance="changed")
        self._denied(order, kw={"update_fields": ["buyer_terms_acceptance"]})

    def test_10_saved_order_update_fields_cannot_extend_expiry(self):
        order = MojPropStarter30Order(id=58)
        self._denied(order, kw={"update_fields": ["expires_at"]})

    def test_11_saved_claim_cannot_reassign_txid(self):
        claim = MojPropStarter30TxClaim(id=59, txid="b" * 64)
        self._denied(claim, kw={"update_fields": ["txid"]})

    def test_12_saved_claim_cannot_reassign_order(self):
        claim = MojPropStarter30TxClaim(id=60, order_id=61)
        self._denied(claim, kw={"update_fields": ["order"]})

    def test_13_saved_order_cannot_reopen_as_issued(self):
        order = MojPropStarter30Order(id=62, status="issued")
        self._denied(order)

    def test_14_saved_claim_cannot_reopen_as_verified(self):
        claim = MojPropStarter30TxClaim(id=63, state="verified")
        self._denied(claim)

    def test_15_order_with_nonadding_state_fails_even_if_pk_missing(self):
        order = MojPropStarter30Order()
        order._state.adding = False
        self._denied(order)

    def test_16_claim_with_nonadding_state_fails_even_if_pk_missing(self):
        claim = MojPropStarter30TxClaim()
        claim._state.adding = False
        self._denied(claim)


if __name__ == "__main__":
    unittest.main()
