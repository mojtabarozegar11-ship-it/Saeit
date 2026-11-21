"""Starter30 persistent order source gates (offline: never touches production DB).

Run: python3 -m unittest tests.test_mojprop_starter30_order_schema_c136 -v
The migration is NOT a license to run migrate on the shared cPanel tenant.
"""
import ast
from pathlib import Path
import unittest

from services.mojprop_starter30_tron_settlement import (
    Starter30PersistedInvoice,
    NativeTRXMatchRejected,
    validate_persisted_order,
)

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "core/models.py"
MIGRATION = ROOT / "core/migrations/0048_mojprop_starter30_order.py"


def classes(path):
    module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return {n.name: n for n in module.body if isinstance(n, ast.ClassDef)}


class NativeStarter30OrderSchemaTests(unittest.TestCase):
    def test_model_and_migration_both_have_dedicated_entities(self):
        m = classes(MODEL)
        g = classes(MIGRATION)
        self.assertIn("MojPropStarter30Order", m)
        self.assertIn("MojPropStarter30TxClaim", m)
        self.assertIn("Migration", g)
        text = MIGRATION.read_text(encoding="utf-8")
        self.assertIn('"0047_mpw_guest_email_recovery"', text)
        self.assertIn('name="MojPropStarter30Order"', text)
        self.assertIn('name="MojPropStarter30TxClaim"', text)

    def test_dedicated_fixed_exact_native_sun_not_reused_usd_quote(self):
        source = MODEL.read_text(encoding="utf-8")
        migration = MIGRATION.read_text(encoding="utf-8")
        for piece in (
            'name="mojprop30_fixed_product"',
            'name="mojprop30_fixed_native_sun"',
            'name="mojprop30_fixed_mainnet"',
            'name="mojprop30_fixed_merchant"',
        ):
            self.assertIn(piece, source)
            self.assertIn(piece, migration)
        self.assertIn('models.Q(amount_sun=30_000_000)', source)
        self.assertIn('models.Q(amount_sun=30000000)', migration)
        self.assertNotIn('currency = models.CharField', source.split("class MojPropStarter30Order", 1)[-1])

    def test_exclusive_unique_transaction_claim_stays_unverified(self):
        source = MODEL.read_text(encoding="utf-8")
        migration = MIGRATION.read_text(encoding="utf-8")
        order = source.split("class MojPropStarter30TxClaim", 1)[1]
        self.assertIn("models.CharField(max_length=64, unique=True)", order)
        self.assertIn('models.Q(state="unverified")', order)
        self.assertIn('name="mojprop30_tx_never_auto_credit"', migration)
        self.assertIn("models.OneToOneField", order)
        self.assertIn("default_permissions = ()", order)

    def test_draft_only_db_constraint_cannot_forge_paid_order(self):
        source = MODEL.read_text(encoding="utf-8")
        migration = MIGRATION.read_text(encoding="utf-8")
        for text in (source, migration):
            self.assertIn('name="mojprop30_draft_only"', text)
            self.assertIn('condition=models.Q(status="draft")', text)
            self.assertNotIn('condition=models.Q(status__in=("draft", "issued"', text)
        self.assertIn('errors["status"] = "This source-only order cannot issue', source)

    def test_source_only_no_payment_activation_or_wallet_transfer(self):
        source = MODEL.read_text(encoding="utf-8").split("class MojPropStarter30Order", 1)[-1]
        self.assertNotIn("broadcast_transaction", source)
        self.assertNotIn("send_mail(", source)
        self.assertNotIn("create_payment_intent", source)
        self.assertNotIn("transfer_trx(", source)

    def test_native_contract_denies_wrong_amount_and_unaccepted_terms(self):
        from services.mojprop_starter30_tron_settlement import (
            PRODUCT, MERCHANT_DOMAIN, MERCHANT_ID, NETWORK,
        )
        invoice = Starter30PersistedInvoice(
            product=PRODUCT, order_ref="MOJPROP30-ABCDE1234567",
            merchant_domain=MERCHANT_DOMAIN, merchant_id=MERCHANT_ID,
            network=NETWORK,
            recipient="THFNU1iEXHd71WjEgjqUksd2UnMg2pUi73",
            amount_sun=30_000_001,
            issued_at_sec=1_790_000_000, expires_at_sec=1_790_003_600,
            buyer_terms_acceptance="terms-accepted-12452",
            payer_hex41="411111111111111111111111111111111111111111",
        )
        with self.assertRaises(NativeTRXMatchRejected):
            validate_persisted_order(invoice)
        invoice = Starter30PersistedInvoice(**{**invoice.__dict__,
            "amount_sun": 30_000_000, "buyer_terms_acceptance": ""})
        with self.assertRaises(NativeTRXMatchRejected):
            validate_persisted_order(invoice)


if __name__ == "__main__":
    unittest.main()
