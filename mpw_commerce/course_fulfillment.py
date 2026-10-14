"""Idempotent local enrollment after a *verified* paid course order.

This is a concrete fulfillment adapter for the EXISTING EducationCourse and
EducationEnrollment tables. It cannot enable new products, approve unpublished
courses, charge buyers or touch other accounts. There is no per-sale merchant
approval. Disabled by default; scheduled invocation is not installed live.
"""
from django.conf import settings
from django.db import transaction

from core.models import EducationCourse, EducationEnrollment, LedgerEntry
from .models import CommerceFulfillment, CommerceInvoice, CommerceReceipt


class CourseFulfillmentUnavailable(ValueError):
    pass


def fulfill_paid_course_item(item_id):
    """Return disabled, blocked, already_completed or enrolled.

    One enrollment per student/course is ensured by existing DB uniqueness.
    A verified receipt AND matching payment ledger are required on every run.
    """
    if (getattr(settings, "MPW_COMMERCE_RELEASE_READY", False) is not True
        or getattr(settings,"MPW_COMMERCE_COURSE_AUTO_ENROLL_ENABLED",False) is not True):
        return "disabled"
    if type(item_id) is not int or item_id<=0:
        raise CourseFulfillmentUnavailable("Invalid course purchase item")
    with transaction.atomic():
        grant=(CommerceFulfillment.objects.select_for_update()
               .select_related("item__order","item__product")
               .filter(item_id=item_id).first())
        if grant is None:
            return "blocked"
        if grant.status==CommerceFulfillment.Status.COMPLETE:
            return "already_completed"
        if grant.kind!="service" or grant.status!=CommerceFulfillment.Status.QUEUED:
            return "blocked"
        item=grant.item
        order=item.order
        product=item.product
        commerce=(product.metadata or {}).get("mpw_commerce")
        if (not isinstance(commerce,dict)
            or commerce.get("fulfillment")!="service"
            or item.quantity!=1
            or order.status!="paid"):
            return "blocked"
        course=(EducationCourse.objects.select_for_update()
                .filter(product_id=item.product_id,active=True,approved=True)
                .first())
        if course is None or course.quality_status not in ("approved","published"):
            return "blocked"
        invoice=(CommerceInvoice.objects.select_related("order")
                 .filter(order=order,status=CommerceInvoice.Status.PAID).first())
        if invoice is None or invoice.total_usd!=order.total:
            return "blocked"
        receipt=CommerceReceipt.objects.filter(invoice=invoice).first()
        if (receipt is None or receipt.network!=invoice.network
            or receipt.recipient.lower()!=invoice.recipient.lower()
            or receipt.amount_atomic!=invoice.amount_atomic
            or receipt.sender.lower()!=invoice.expected_sender.lower()
            or receipt.backend!=invoice.network+"-verified"):
            return "blocked"
        if not LedgerEntry.objects.filter(
            order=order,entry_type="payment",payment_intent__isnull=True,
            currency="USD",amount=order.total,
            reference="mpw-commerce:"+receipt.network+":"+receipt.tx_hash,
            metadata__commerce_invoice_id=invoice.pk,
            metadata__evidence_digest=receipt.evidence_digest,
        ).exists():
            return "blocked"
        enrollment,created=EducationEnrollment.objects.get_or_create(
            course=course,user_id=order.customer_id,
            defaults={"status":"active","source":"mpw_commerce"},
        )
        # Never silently reactivate an explicitly cancelled enrollment.
        if enrollment.status!="active":
            return "blocked"
        grant.status=CommerceFulfillment.Status.COMPLETE
        grant.save(update_fields=["status","updated_at"])
        return "enrolled" if created else "already_enrolled"


def fulfill_course_batch(limit=100):
    """One bounded database-only pass; no background network polling."""
    if getattr(settings,"MPW_COMMERCE_COURSE_AUTO_ENROLL_ENABLED",False) is not True:
        return {"state":"disabled","processed":0,"enrolled":0}
    if type(limit) is not int or limit<=0 or limit>100:
        raise CourseFulfillmentUnavailable("Unsafe batch size")
    waiting=list(CommerceFulfillment.objects.filter(
        kind="service",status="queued",item__order__status="paid",
        item__product__education_course__isnull=False,
    ).order_by("id").values_list("item_id",flat=True)[:limit+1])
    if len(waiting)>limit:
        raise CourseFulfillmentUnavailable("Course activation batch overflow")
    activated=0
    for item_id in waiting:
        if fulfill_paid_course_item(item_id)=="enrolled":
            activated+=1
    return {"state":"processed","processed":len(waiting),"enrolled":activated}
