"""Historical walletless paid item entitlement — no DB writes, no mail, no download."""
import json
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase, override_settings

from core.crown_tron_receipts import PROVIDER
from services.mojtaba_tron_owner_receiver import APPROVED_NATIVE_TRX_RECIPIENT
from services.mpw_walletless_existing_paid_access import (
    verified_existing_walletless_item_access as decide,
)

ROOT = Path(__file__).resolve().parents[1]


def fixture():
    user = SimpleNamespace(pk=201, is_authenticated=True, is_active=True)
    p = SimpleNamespace(pk=72, active=True, product_type="digital_book")
    order = SimpleNamespace(pk=101, customer_id=201, status="paid",
                            currency="USD", total=Decimal("7.50"))
    intent = SimpleNamespace(
        order_id=101, provider=PROVIDER, status="paid", currency="USD",
        amount=Decimal("7.50"), provider_reference=json.dumps({
            "v": 1, "to": APPROVED_NATIVE_TRX_RECIPIENT,
            "sun": 9000000, "rate": "1", "at": "2026-11-15T20:00:00+00:00",
        }),
    )
    order.payment_intent = intent
    item = SimpleNamespace(pk=301, order=order, product=p, currency="USD",
                           quantity=1, unit_price=Decimal("7.50"))
    return user, item


class HistoricalWalletlessPaidDigitalAccessTests(SimpleTestCase):
    def setUp(self):
        self.user, self.item = fixture()
        self.asset_check = lambda product: product is self.item.product
        self.item_queryset = Mock()
        self.item_queryset.select_related.return_value.first.return_value = self.item
        self.order_items = patch("core.models.OrderItem")
        self.OrderItem = self.order_items.start()
        self.OrderItem.objects.filter.return_value = self.item_queryset

        self.ledger_rows = Mock()
        self.ledger_rows.exists.return_value = False
        self.ledger = patch("core.models.LedgerEntry")
        self.LedgerEntry = self.ledger.start()
        self.LedgerEntry.objects.filter.return_value = self.ledger_rows

        related = SimpleNamespace(_meta=SimpleNamespace(label_lower="core.orderitem"))
        field = SimpleNamespace(related_model=related)
        self.grant = Mock()
        self.grant._meta.get_field.return_value = field
        self.grant.objects.filter.return_value.exists.return_value = True
        self.invoice = Mock()
        parent = SimpleNamespace(_meta=SimpleNamespace(label_lower="core.order"))
        self.invoice._meta.get_field.return_value = SimpleNamespace(
            related_model=parent
        )
        self.invoice.objects.filter.return_value.exists.return_value = False
        self.model = patch(
            "django.apps.apps.get_model",
            side_effect=lambda app, name: {
                "CommerceInvoice": self.invoice,
                "CommerceFulfillment": self.grant,
            }[name],
        )
        self.model.start()

        self.credit = patch("services.mpw_walletless_existing_paid_access.verified_walletless_credit",
                            return_value=True)
        self.credit.start()
        self.enabled = override_settings(
            MPW_WALLETLESS_EXISTING_PAID_DIGITAL_ACCESS_ENABLED=True,
        )
        self.enabled.enable()

    def tearDown(self):
        self.enabled.disable()
        self.credit.stop()
        self.model.stop()
        self.ledger.stop()
        self.order_items.stop()

    def allowed(self, user=None, item_id=301, check=None):
        return decide(self.user if user is None else user, item_id,
                      asset_is_releasable=self.asset_check if check is None else check)

    def test_strictly_paid_same_buyer_real_ledger_ready_file_can_pass(self):
        self.assertTrue(self.allowed())

    def test_feature_flag_default_off_fails_before_db_access(self):
        with override_settings(MPW_WALLETLESS_EXISTING_PAID_DIGITAL_ACCESS_ENABLED=False):
            self.assertFalse(self.allowed())
        self.assertTrue(self.allowed())

    def test_wrong_buyer_never_gets_another_order(self):
        actor = SimpleNamespace(pk=202, is_authenticated=True, is_active=True)
        self.assertFalse(self.allowed(user=actor))

    def test_anonymous_never_gets_access(self):
        actor = SimpleNamespace(pk=201, is_authenticated=False, is_active=True)
        self.assertFalse(self.allowed(user=actor))

    def test_inactive_account_never_gets_access(self):
        actor = SimpleNamespace(pk=201, is_authenticated=True, is_active=False)
        self.assertFalse(self.allowed(user=actor))

    def test_bool_user_primary_key_not_int(self):
        actor = SimpleNamespace(pk=True, is_authenticated=True, is_active=True)
        self.assertFalse(self.allowed(user=actor))

    def test_bool_item_id_not_int(self):
        self.assertFalse(self.allowed(item_id=True))

    def test_nonpositive_item_id_denied(self):
        self.assertFalse(self.allowed(item_id=0))

    def test_missing_order_item_denied(self):
        self.item_queryset.select_related.return_value.first.return_value = None
        self.assertFalse(self.allowed())

    def test_unpaid_order_denied(self):
        self.item.order.status = "pending"
        self.assertFalse(self.allowed())

    def test_unpaid_walletless_intent_denied(self):
        self.item.order.payment_intent.status = "awaiting"
        self.assertFalse(self.allowed())

    def test_other_payment_provider_cannot_replay(self):
        self.item.order.payment_intent.provider = "demo"
        self.assertFalse(self.allowed())

    def test_wrong_currency_denied(self):
        self.item.currency = "IRR"
        self.assertFalse(self.allowed())

    def test_wrong_intent_total_denied(self):
        self.item.order.payment_intent.amount = Decimal("1")
        self.assertFalse(self.allowed())

    def test_wrong_recipient_not_equal_owner_wallet(self):
        self.item.order.payment_intent.provider_reference = json.dumps({
            "to": "TAAOtherRecipientNotApproved123", "sun": 9000000,
        })
        self.assertFalse(self.allowed())

    def test_invalid_receipt_reference_denied(self):
        self.item.order.payment_intent.provider_reference = "{bad json"
        self.assertFalse(self.allowed())

    def test_zero_sun_not_a_real_transfer(self):
        self.item.order.payment_intent.provider_reference = json.dumps({
            "to": APPROVED_NATIVE_TRX_RECIPIENT, "sun": 0,
        })
        self.assertFalse(self.allowed())

    def test_explicit_digital_product_is_eligible(self):
        self.item.product.product_type = "digital"
        self.assertTrue(self.allowed())

    def test_explicit_digital_book_product_is_eligible(self):
        self.item.product.product_type = "digital_book"
        self.assertTrue(self.allowed())

    def test_physical_goods_cannot_be_unlocked_as_pdf(self):
        self.item.product.product_type = "physical"
        self.assertFalse(self.allowed())

    def test_undefined_product_type_denied(self):
        self.item.product.product_type = None
        self.assertFalse(self.allowed())

    def test_unrecognized_product_type_denied(self):
        self.item.product.product_type = "bundle"
        self.assertFalse(self.allowed())

    def test_service_subscription_not_digital_download(self):
        self.item.product.product_type = "signals"
        self.assertFalse(self.allowed())

    def test_digital_type_is_case_sensitive(self):
        self.item.product.product_type = "Digital"
        self.assertFalse(self.allowed())

    def test_blank_product_type_denied(self):
        self.item.product.product_type = ""
        self.assertFalse(self.allowed())

    def test_numeric_product_type_denied(self):
        self.item.product.product_type = 1
        self.assertFalse(self.allowed())

    def test_truthy_list_product_type_denied(self):
        self.item.product.product_type = ["digital"]
        self.assertFalse(self.allowed())

    def test_digital_content_past_refund_stays_revoked(self):
        self.item.product.product_type = "digital"
        self.ledger_rows.exists.return_value = True
        self.assertFalse(self.allowed())

    def test_unknown_kind_denied_before_asset_resolver(self):
        self.item.product.product_type = "unclassified"
        resolver = Mock(return_value=True)
        self.assertFalse(self.allowed(check=resolver))
        resolver.assert_not_called()

    def test_game_cosmetic_not_a_download(self):
        self.item.product.product_type = "game_cosmetic"
        self.assertFalse(self.allowed())

    def test_inactive_product_not_accessible(self):
        self.item.product.active = False
        self.assertFalse(self.allowed())

    def test_nonpositive_item_quantity_denied(self):
        self.item.quantity = 0
        self.assertFalse(self.allowed())

    def test_refund_or_chargeback_blocks_item_access(self):
        self.ledger_rows.exists.return_value = True
        self.assertFalse(self.allowed())

    def test_unverified_stored_credit_never_unlocks(self):
        with patch("services.mpw_walletless_existing_paid_access.verified_walletless_credit",return_value=False):
            self.assertFalse(self.allowed())

    def test_entitlement_fulfillment_missing_blocks_item_access(self):
        self.grant.objects.filter.return_value.exists.return_value = False
        self.assertFalse(self.allowed())

    def test_foreign_commerce_item_fk_not_core_orderitem_denied(self):
        other = SimpleNamespace(_meta=SimpleNamespace(label_lower="mpw_commerce.commerceitem"))
        self.grant._meta.get_field.return_value.related_model = other
        self.assertFalse(self.allowed())

    def test_existing_commerce_invoice_forces_standard_authorization_path(self):
        self.invoice.objects.filter.return_value.exists.return_value = True
        self.assertFalse(self.allowed())

    def test_wrong_commerce_invoice_order_fk_denied(self):
        foreign = SimpleNamespace(
            _meta=SimpleNamespace(label_lower="mpw_commerce.commerceorder")
        )
        self.invoice._meta.get_field.return_value.related_model = foreign
        self.assertFalse(self.allowed())

    def test_private_file_unavailable_blocks_access(self):
        self.assertFalse(self.allowed(check=lambda _: False))

    def test_private_file_check_must_be_strict_true(self):
        self.assertFalse(self.allowed(check=lambda _: "yes"))

    def test_private_file_check_exception_fails_closed(self):
        def boom(_):
            raise RuntimeError("private file unavailable")
        self.assertFalse(self.allowed(check=boom))

    def test_file_check_must_be_callable(self):
        self.assertFalse(self.allowed(check=False))

    def test_deleted_related_product_or_order_denied_without_server_error(self):
        for related in ("order", "product"):
            with self.subTest(related=related):
                old = getattr(self.item, related)
                setattr(self.item, related, None)
                try:
                    self.assertFalse(self.allowed())
                finally:
                    setattr(self.item, related, old)

    def test_nonfinite_paid_order_total_never_grants_access(self):
        for bad in (Decimal("NaN"), Decimal("Infinity"),
                    Decimal("-Infinity"), Decimal("sNaN")):
            with self.subTest(bad=str(bad)):
                original = self.item.order.total
                self.item.order.total = bad
                try:
                    self.assertFalse(self.allowed())
                finally:
                    self.item.order.total = original

    def test_nonfinite_item_unit_price_never_grants_access(self):
        for bad in (Decimal("NaN"), Decimal("Infinity"),
                    Decimal("-Infinity"), Decimal("sNaN")):
            with self.subTest(bad=str(bad)):
                original = self.item.unit_price
                self.item.unit_price = bad
                try:
                    self.assertFalse(self.allowed())
                finally:
                    self.item.unit_price = original

    def test_non_decimal_amounts_never_grant_historical_access(self):
        for obj, field in ((self.item.order, "total"),
                           (self.item, "unit_price"),
                           (self.item.order.payment_intent, "amount")):
            for bad in (None, "7.50", 7.5, True):
                with self.subTest(field=field, bad=repr(bad)):
                    original = getattr(obj, field)
                    setattr(obj, field, bad)
                    try:
                        self.assertFalse(self.allowed())
                    finally:
                        setattr(obj, field, original)

    def test_missing_or_corrupt_payment_intent_denied_without_500(self):
        order = self.item.order
        original = order.payment_intent
        try:
            order.payment_intent = None
            self.assertFalse(self.allowed())
            del order.payment_intent
            self.assertFalse(self.allowed())
        finally:
            order.payment_intent = original

    def test_missing_persisted_provider_reference_denied_without_500(self):
        intent = self.item.order.payment_intent
        original = intent.provider_reference
        try:
            del intent.provider_reference
            self.assertFalse(self.allowed())
        finally:
            intent.provider_reference = original

    def test_paid_item_read_database_outage_denies_access(self):
        self.OrderItem.objects.filter.side_effect = ConnectionError("db unavailable")
        self.assertFalse(self.allowed())

    def test_refund_ledger_outage_is_not_permission_to_unlock(self):
        self.ledger_rows.exists.side_effect = RuntimeError("ledger unavailable")
        self.assertFalse(self.allowed())

    def test_no_live_financial_or_download_action_in_module(self):
        code = (ROOT / "services/mpw_walletless_existing_paid_access.py").read_text()
        for bad in ("objects.create(", "objects.update(", ".save(", ".delete(",
                    "broadcasttransaction", "sendrawtransaction",
                    "requests.post(", "urllib.request", "send_mail(",
                    "FileResponse(", "file.open(", "open(", "pathlib.Path("):
            with self.subTest(bad=bad):
                self.assertNotIn(bad, code)
        self.assertIn('"MPW_WALLETLESS_EXISTING_PAID_DIGITAL_ACCESS_ENABLED"', code)

    def test_django_release_flag_disabled_in_source_defaults(self):
        settings = (ROOT / "config/settings.py").read_text()
        self.assertIn('"MPW_WALLETLESS_EXISTING_PAID_DIGITAL_ACCESS_ENABLED", default=False', settings)

    def test_never_copy_to_unauthorized_user_and_never_forge_invoice(self):
        code = (ROOT / "services/mpw_walletless_existing_paid_access.py").read_text()
        self.assertIn('order__customer_id=user.pk', code)
        self.assertIn('verified_walletless_credit(order, intent) is not True', code)
        self.assertIn('entry_type__in=("refund", "reversal", "chargeback")', code)
        self.assertIn('item_id=item.pk, status__in=_ALLOWED_READY', code)
        self.assertNotIn("CommerceInvoice.objects", code)
        self.assertNotIn("CommerceReceipt.objects", code)
