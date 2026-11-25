from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from core.models import Agent, Product, Order, OrderItem
from mpw_commerce.signal_subscriptions import subscription_product_terms, subscription_sale_ready
from mpw_commerce.signal_research_delivery import publish_reviewed_issue
from services.mojtaba_signal_policy import EducationalSignal, RISK_DISCLAIMER
from services.mpw_walletless_commercial_intent import _ready_order
from services.mpw_trx_walletless_core import PaymentHold


class SubscriptionCheckoutTests(TestCase):
    def setUp(self):
        self.buyer = get_user_model().objects.create_user(username="sub_checkout_buyer")
        self.reviewer = get_user_model().objects.create_user(
            username="sub_checkout_reviewer", is_staff=True, is_superuser=True)
        self.product = Product.objects.create(
            title="Monthly research", product_type="subscription",
            price=Decimal("29.90"), currency="USD", active=True,
            metadata={"signal_plan_id": "education-monthly", "rights_cleared": True,
                      "mpw_commerce": {"enabled": True, "fulfillment": "subscription"}})
        self.config = SimpleNamespace(MPW_SIGNAL_SUBSCRIPTION_RELEASE_APPROVED=True,
                                      MPW_TRX_PUBLIC_PRODUCT_IDS=(self.product.pk,))
        self.order = Order.objects.create(customer=self.buyer, total=self.product.price,
                                          currency="USD", status="pending")
        self.item = OrderItem.objects.create(order=self.order, product=self.product,
                                             quantity=1, unit_price=self.product.price,
                                             currency="USD")

    def issue(self, record_id, asset, url):
        moment = timezone.now()
        record = EducationalSignal(
            record_id=record_id, asset=asset, timeframe="1w",
            scenario="Illustrative educational research scenario with no promised result.",
            invalidation="A later observation invalidates this educational scenario.",
            evidence_url=url, observed_at=moment, reviewed_at=moment,
            reviewer_id=self.reviewer.username, risk_statement=RISK_DISCLAIMER,
            as_of=moment)
        return publish_reviewed_issue(record, reviewer=self.reviewer,
                                      source_bytes=b"fixture", rights_reference="Fixture only")

    def test_approval_and_both_fresh_sources_required(self):
        self.assertEqual(subscription_product_terms(self.product)["term_weeks"], 4)
        self.assertFalse(subscription_sale_ready(self.product, config=self.config))
        Agent.objects.create(code="mojtaba-bot-ai", name="Mojtaba.bot.ai",
                             mission="Educational research", active=True)
        self.issue("ecb_fx_test", "EUR-FX", "https://www.ecb.europa.eu/")
        self.assertFalse(subscription_sale_ready(self.product, config=self.config))
        self.issue("eia_oil_test", "OIL-INVENTORY", "https://www.eia.gov/")
        self.assertTrue(subscription_sale_ready(self.product, config=self.config))
        self.config.MPW_SIGNAL_SUBSCRIPTION_RELEASE_APPROVED = False
        self.assertFalse(subscription_sale_ready(self.product, config=self.config))

    def test_invoice_order_snapshots_only_ready_subscription(self):
        with self.assertRaises(PaymentHold):
            _ready_order(self.order, buyer_id=self.buyer.pk)
        with patch("mpw_commerce.signal_subscriptions.subscription_sale_ready", return_value=True):
            total, item = _ready_order(self.order, buyer_id=self.buyer.pk)
            self.assertEqual(total, Decimal("29.90"))
            self.assertEqual(item.mpw_signal_subscription.plan_id, "education-monthly")
