"""Actual educational enrollment after trusted paid ETH/TRX order (offline).

Uses the existing course/enrollment DB schema, no fake enrollment backend, no
merchant consent per purchase, no external funding or network transactions.
"""
from datetime import timedelta
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase,override_settings
from django.utils import timezone

from core.models import (
    Product,Order,OrderItem,EducationTrack,EducationCourse,EducationEnrollment,
    LedgerEntry,
)
from mpw_commerce.invoicing import (
    reserve_order_invoice,VerifiedBuyer,TrustedRate,
)
from mpw_commerce.settlement import settle_order_invoice
from mpw_commerce.course_fulfillment import (
    fulfill_paid_course_item,fulfill_course_batch,
)
from mpw_commerce.models import CommerceFulfillment


FLAGS={
    "MPW_COMMERCE_RELEASE_READY":True,
    "MPW_COMMERCE_INVOICING_ENABLED":True,
    "MPW_COMMERCE_SETTLEMENT_ENABLED":True,
    "MPW_COMMERCE_COURSE_AUTO_ENROLL_ENABLED":True,
}
TX="0x"+"d"*64
SENDER="0x"+"c"*40


class PaidCourseFulfillmentTests(TestCase):
    def setUp(self):
        self.now=timezone.now()
        self.buyer=get_user_model().objects.create_user(username="course-buyer-01")
        self.stranger=get_user_model().objects.create_user(username="course-stranger")
        self.product=Product.objects.create(
            title="Online training",product_type="service",active=True,
            price=Decimal("45.00"),currency="USD",
            metadata={"mpw_commerce":{"enabled":True,"fulfillment":"service"}},
        )
        self.track=EducationTrack.objects.create(
            title="Training laboratory",description="A test track"
        )
        self.course=EducationCourse.objects.create(
            track=self.track,title="Sample course",slug="ci-sample-course",
            summary="Test only",price=Decimal("45.00"),currency="USD",
            active=True,approved=True,quality_status="published",
            product=self.product,
        )
        self.order=Order.objects.create(
            customer=self.buyer,status="pending",currency="USD",
            total=Decimal("45.00"),
        )
        self.item=OrderItem.objects.create(
            order=self.order,product=self.product,quantity=1,
            unit_price=Decimal("45.00"),currency="USD",
        )
        self.flags=override_settings(**FLAGS)
        self.flags.enable()
        self.addCleanup(self.flags.disable)

    def paid_invoice(self):
        invoice=reserve_order_invoice(
            self.order.pk,"ETH",
            buyer=VerifiedBuyer(
                sender=SENDER,challenge_id="ci-signed-customer",
                verified_at=self.now,
            ),
            quote=TrustedRate(
                usd_per_asset=Decimal("3000.00"),
                source="coingecko",observed_at=self.now,
            ),
            now=self.now,
        )
        proof={
            "finalized":True,"order_id":self.order.pk,
            "network":invoice.network,"tx_hash":TX,
            "sender":SENDER,
            "recipient":invoice.recipient.lower(),
            "amount_atomic":int(invoice.amount_atomic),
            "backend":"ethereum-mainnet-verified",
            "block_timestamp":invoice.issued_at+timedelta(seconds=12),
        }
        self.assertEqual(
            settle_order_invoice(
                invoice.pk,TX,trusted_chain_verifier=lambda *_:proof,
            ),
            "paid",
        )
        return invoice

    def test_unpaid_course_cannot_create_enrollment(self):
        self.assertEqual(fulfill_paid_course_item(self.item.pk),"blocked")
        self.assertFalse(EducationEnrollment.objects.exists())

    def test_paid_order_activates_real_course_once_without_owner_approval(self):
        self.paid_invoice()
        self.assertEqual(self.item.mpw_fulfillment.status,"queued")
        self.assertEqual(fulfill_paid_course_item(self.item.pk),"enrolled")
        enrollment=EducationEnrollment.objects.get(
            user=self.buyer,course=self.course,
        )
        self.assertEqual(enrollment.status,"active")
        self.assertEqual(enrollment.source,"mpw_commerce")
        self.assertEqual(self.item.mpw_fulfillment.status,"complete")
        self.assertEqual(fulfill_paid_course_item(self.item.pk),"already_completed")
        self.assertEqual(EducationEnrollment.objects.count(),1)
        self.assertFalse(EducationEnrollment.objects.filter(
            user=self.stranger,
        ).exists())

    def test_batch_automatically_processes_verified_paid_order(self):
        self.paid_invoice()
        results=fulfill_course_batch()
        self.assertEqual(results["processed"],1)
        self.assertEqual(results["enrolled"],1)
        self.assertEqual(fulfill_course_batch()["processed"],0)
        self.assertTrue(EducationEnrollment.objects.filter(
            user=self.buyer,course=self.course,status="active",
        ).exists())

    def test_disabled_switch_blocks_enrollment_automatically(self):
        self.paid_invoice()
        with override_settings(MPW_COMMERCE_COURSE_AUTO_ENROLL_ENABLED=False):
            self.assertEqual(fulfill_paid_course_item(self.item.pk),"disabled")
            self.assertEqual(fulfill_course_batch()["state"],"disabled")
        self.assertFalse(EducationEnrollment.objects.exists())

    def test_missing_payment_ledger_never_creates_enrollment(self):
        self.paid_invoice()
        LedgerEntry.objects.filter(order=self.order).delete()
        self.assertEqual(fulfill_paid_course_item(self.item.pk),"blocked")
        self.assertFalse(EducationEnrollment.objects.exists())

    def test_inactive_or_unapproved_course_does_not_activate(self):
        self.paid_invoice()
        self.course.approved=False
        self.course.save(update_fields=["approved"])
        self.assertEqual(fulfill_paid_course_item(self.item.pk),"blocked")
        self.assertFalse(EducationEnrollment.objects.exists())

    def test_cancelled_enrollment_not_silently_reactivated(self):
        self.paid_invoice()
        EducationEnrollment.objects.create(
            user=self.buyer,course=self.course,
            status="cancelled",source="admin",
        )
        self.assertEqual(fulfill_paid_course_item(self.item.pk),"blocked")
        self.assertEqual(EducationEnrollment.objects.get(
            user=self.buyer,course=self.course,
        ).status,"cancelled")
        self.assertEqual(self.item.mpw_fulfillment.status,"queued")
