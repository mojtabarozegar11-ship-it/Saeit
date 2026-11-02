"""Conservative, audit-backed publishing. No financial spend or blind retry."""
from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone
from ecosystem_hub.access import require_unit
from company_messaging.services import ProviderNotReady
from company_messaging.domestic_providers import send_bot_message
from .models import AUTOMATED_PLATFORMS, Publication, PublicationEvent


def approve_publication(pk, actor):
    if not (actor.is_superuser or actor.has_perm("company_marketing.approve_publication")):
        raise PermissionDenied("مجوز تأیید انتشار ندارید.")
    with transaction.atomic():
        item = Publication.objects.select_for_update().select_related("campaign", "channel").get(pk=pk)
        require_unit(actor, item.campaign.unit, write=True)
        if item.status != "draft":
            raise ValidationError("فقط نسخه پیش‌نویس قابل تأیید است.")
        if not item.rights_reference.strip():
            raise ValidationError("مرجع حقوق محتوا ثبت نشده است.")
        if not item.channel.active or not item.channel.is_company_owned or not item.channel.verified_at:
            raise ValidationError("حساب سازمانی مقصد هنوز احراز نشده است.")
        item.content_sha256 = item.payload_hash()
        item.approved_at = timezone.now()
        item.approved_by = actor
        item.status = "approved"
        item.save()
        PublicationEvent.objects.create(publication=item, code="manager_approved")
        return item


def dispatch_publication(pk):
    """At most one handoff. An ambiguous network result must be reconciled manually."""
    if not (getattr(settings, "COMPANY_MARKETING_PUBLISH_ENABLED", False)
            and getattr(settings, "COMPANY_MESSAGING_SEND_ENABLED", False)):
        return "disabled"
    with transaction.atomic():
        item = Publication.objects.select_for_update().select_related("campaign", "channel").get(pk=pk)
        if item.status != "approved" or item.scheduled_at > timezone.now():
            return "not_due"
        if (item.campaign.status != "active" or item.channel.platform not in AUTOMATED_PLATFORMS
                or item.campaign.starts_on > timezone.localdate()
                or (item.campaign.ends_on and item.campaign.ends_on < timezone.localdate())):
            item.status = "blocked"
            item.error_code = "campaign_inactive_or_connector_unsupported"
            item.save()
            PublicationEvent.objects.create(publication=item, code="blocked")
            return "blocked"
        try:
            item.full_clean()
        except ValidationError:
            item.status = "blocked"
            item.error_code = "rights_or_ownership_invalid"
            item.save(update_fields=["status", "error_code"])
            PublicationEvent.objects.create(publication=item, code="blocked")
            return "blocked"
        item.status = "sending"
        item.attempts += 1
        item.save(update_fields=["status", "attempts"])
        PublicationEvent.objects.create(publication=item, code="external_handoff")
        platform = item.channel.platform
        destination = item.channel.destination
        payload = item.content + ("\n" + item.landing_url if item.landing_url else "")
    try:
        upstream = send_bot_message(platform, destination, payload)
    except ProviderNotReady:
        status, reason = "blocked", "connector_not_configured"
    except Exception:
        status, reason = "uncertain", "provider_outcome_unknown"
    else:
        status, reason = "accepted", ""
    with transaction.atomic():
        item = Publication.objects.select_for_update().get(pk=pk)
        if item.status != "sending":
            return "manual_review"
        item.status = status
        item.error_code = reason
        if status == "accepted":
            item.provider_reference = upstream
            item.accepted_at = timezone.now()
        item.save(update_fields=["status", "error_code", "provider_reference", "accepted_at"])
        PublicationEvent.objects.create(publication=item, code=status)
    return status
