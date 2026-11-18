"""Safe B2B intake, signed status receipt and public trust information."""
import logging
from django.conf import settings
from django.core import signing
from django.core.mail import send_mail
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST
from .company_content_views import CompanyInquiryForm
from .company_inquiry_models import CompanyInquiry

log = logging.getLogger(__name__)
SALT = "zomorod-b2b-receipt-v1"

def _reference(lead):
    return "ZM-%s-%06d" % (lead.created_at.strftime("%Y%m%d"), lead.pk)

def _staff_notice(lead_id):
    if not getattr(settings, "COMPANY_INQUIRY_NOTIFICATION_ENABLED", False):
        return
    to = str(getattr(settings, "COMPANY_TRADE_EMAIL", "") or "").strip()
    sender = str(getattr(settings, "DEFAULT_FROM_EMAIL", "") or "").strip()
    if not (to and sender and getattr(settings, "EMAIL_HOST", "")):
        log.warning("B2B notice skipped: no verified SMTP configuration")
        return
    try:
        lead = CompanyInquiry.objects.get(pk=lead_id)
        send_mail(
            "New Zomorod Melal inquiry: " + _reference(lead),
            "Reference: %s\nCategory: %s\nSubject: %s\nReview the private CRM record." % (
                _reference(lead), lead.get_kind_display(), lead.subject),
            sender, [to], fail_silently=False)
    except Exception:
        log.exception("B2B notice delivery failed for record %s", lead_id)

@require_POST
def submit_company_inquiry(request):
    english = request.POST.get("language") == "en"
    form = CompanyInquiryForm(request.POST)
    if request.POST.get("company_url") or not form.is_valid():
        return render(request, "core/company_inquiry_error.html", {
            "form": form if not request.POST.get("company_url") else CompanyInquiryForm(),
            "english": english,
        }, status=400)
    with transaction.atomic():
        lead = form.save()
        transaction.on_commit(lambda: _staff_notice(lead.pk))
    token = signing.dumps({"id": lead.pk}, salt=SALT)
    url = reverse("company_inquiry_receipt", kwargs={"token": token})
    return redirect(url + ("?lang=en" if english else ""))

@require_GET
def company_inquiry_receipt(request, token):
    try:
        data = signing.loads(token, salt=SALT, max_age=365*24*60*60)
        identifier = data["id"]
        if type(identifier) is not int or identifier <= 0:
            raise Http404("Invalid receipt")
    except (signing.BadSignature, KeyError, TypeError, ValueError) as exc:
        raise Http404("Invalid receipt") from exc
    lead = get_object_or_404(CompanyInquiry, pk=identifier)
    response = render(request, "core/company_inquiry_receipt.html", {
        "reference": _reference(lead),
        "status": lead.get_status_display(),
        "received_at": lead.created_at,
        "english": request.GET.get("lang") == "en",
    })
    response["Cache-Control"] = "private, no-store"
    response["X-Robots-Tag"] = "noindex, nofollow"
    return response

@require_GET
def b2b_partners(request):
    return render(request, "core/b2b_partners.html")

@require_GET
def company_privacy(request):
    return render(request, "core/company_privacy.html")
