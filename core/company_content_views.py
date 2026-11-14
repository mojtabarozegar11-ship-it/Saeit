from django import forms
from django.http import Http404
from django.shortcuts import render
from django.utils import timezone
from .company_content_models import CompanyContentLink, CompanyGalleryMedia
from .newsletter_models import NewsletterStory
from .company_inquiry_models import CompanyInquiry


def company_gallery(request):
    media = CompanyGalleryMedia.objects.filter(published=True, published_at__lte=timezone.now()).select_related("newsletter_story")
    kind = request.GET.get("type", "").strip().lower()
    if kind in {"image", "video"}:
        media = media.filter(media_type=kind)
    query = request.GET.get("q", "").strip()
    if query:
        media = media.filter(title__icontains=query)
    return render(request, "core/company_gallery.html", {"media": media[:100], "query": query, "kind": kind})


def company_content_feed(request, slug):
    target = f"/company/{slug.strip('/')}/" if slug != "company" else "/company/"
    links = CompanyContentLink.objects.filter(target_path=target).select_related("newsletter_story", "knowledge_article")
    links = [x for x in links if (x.newsletter_story and x.newsletter_story.status == "published") or (x.knowledge_article and x.knowledge_article.published)]
    if not links:
        raise Http404("Company content feed not found")
    return render(request, "core/company_content_feed.html", {"target": target, "links": links})


class CompanyInquiryForm(forms.ModelForm):
    """Validate explicit-consent leads before storing in the existing CRM."""

    consent = forms.BooleanField(required=True, label="با ثبت درخواست و بررسی اطلاعات برای پاسخ‌گویی موافقم")
    website = forms.CharField(required=False, widget=forms.HiddenInput)

    message = forms.CharField(max_length=5000, strip=True)

    class Meta:
        model = CompanyInquiry
        fields = ("kind", "name", "organization", "email", "phone", "subject", "message")

    def clean_website(self):
        if self.cleaned_data.get("website"):
            raise forms.ValidationError("درخواست نامعتبر است")
        return ""


# Session-only duplicate and intake-rate defenses; do not claim global anti-spam.
_DUPLICATE_WINDOW_SECONDS = 15 * 60
_SESSION_KEY = "zomorod_last_company_inquiry_v1"
_RATE_KEY = "zomorod_company_inquiry_submissions_v1"
_RATE_WINDOW_SECONDS = 60 * 60
_RATE_NEW_LEADS = 6


def _inquiry_fingerprint(cleaned):
    import json
    from django.utils.crypto import salted_hmac
    fields = ("kind", "name", "organization", "email", "phone", "subject", "message")
    content = json.dumps(
        {key: cleaned.get(key, "") for key in fields},
        ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    )
    return salted_hmac("company.inquiry.duplicate.v1", content).hexdigest()


def company_portal_home(request, *, service=None):
    """Write a real CRM lead once, return signed receipt; never send mail."""
    from django.shortcuts import redirect
    from django.urls import reverse
    if request.method != "POST":
        raise Http404("Use the company intake form")

    data = request.POST.copy()
    if service == "farm":
        data["kind"] = "commercial"
        data["subject"] = "ZM-FARM | درخواست تحلیل اقتصادی مزرعه"
    form = CompanyInquiryForm(data)
    if not form.is_valid():
        response = render(request, "core/company_inquiry_retry.html", {
            "form": form,
            "form_action": "/company/farm-economics/request/" if service == "farm" else "/company/",
        }, status=400)
        response["Cache-Control"] = "no-store"
        response["Referrer-Policy"] = "no-referrer"
        response["X-Robots-Tag"] = "noindex, nofollow"
        return response

    from django.utils import timezone
    from .company_inquiry_receipts import issue_receipt
    fingerprint = _inquiry_fingerprint(form.cleaned_data)
    record = request.session.get(_SESSION_KEY)
    now = int(timezone.now().timestamp())
    if (type(record) is dict and record.get("fingerprint") == fingerprint
            and type(record.get("created")) is int
            and 0 <= now - record["created"] < _DUPLICATE_WINDOW_SECONDS
            and type(record.get("inquiry_id")) is int
            and CompanyInquiry.objects.filter(pk=record["inquiry_id"]).exists()):
        return redirect(reverse("company_inquiry_receipt", kwargs={
            "ticket": issue_receipt(record["inquiry_id"]),
        }))

    # Rate-limit only *new* lead creation; repeat of a previously saved request
    # above returns its existing receipt without counting another submission.
    recent = request.session.get(_RATE_KEY, [])
    if type(recent) is not list:
        recent = []
    recent = [
        t for t in recent if type(t) is int
        and 0 <= now - t < _RATE_WINDOW_SECONDS
    ]
    if len(recent) >= _RATE_NEW_LEADS:
        from django.http import HttpResponse
        response = HttpResponse(
            "سقف درخواست‌های این نشست موقتاً تکمیل شده است؛ بعداً اقدام کنید.",
            status=429, content_type="text/plain; charset=utf-8",
        )
        response["Cache-Control"] = "no-store"
        response["Referrer-Policy"] = "no-referrer"
        response["Retry-After"] = str(_RATE_WINDOW_SECONDS)
        return response

    # Keep a server-generated *non-sensitive* consent provenance in the
    # pre-existing internal CRM notes field (no live migration, no PII echo).
    # This marker is administrative evidence, not immutable legal certification.
    from django.utils import timezone as django_timezone
    created = django_timezone.now().isoformat(timespec="seconds")
    origin = "farm" if service == "farm" else "company"
    inquiry = form.save(commit=False)
    inquiry.internal_note = (
        "INTAKE_CONSENT_V1; confirmed_at=" + created + "; source=" + origin
    )
    inquiry.save()
    recent.append(now)
    request.session[_RATE_KEY] = recent
    request.session[_SESSION_KEY] = {
        "fingerprint": fingerprint, "created": now, "inquiry_id": inquiry.pk,
    }
    return redirect(reverse("company_inquiry_receipt", kwargs={
        "ticket": issue_receipt(inquiry.pk),
    }))


def company_inquiry_receipt(request, ticket):
    """Signed, privacy-minimal 30-day status check; no anonymous CRM PII."""
    from django.views.decorators.cache import never_cache
    from django.views.decorators.http import require_GET
    from .company_inquiry_receipts import verify_receipt

    @never_cache
    @require_GET
    def _show(request, ticket):
        inquiry_id = verify_receipt(ticket)
        status = CompanyInquiry.objects.filter(pk=inquiry_id).values_list("status", flat=True).first()
        if status is None:
            raise Http404("Receipt not found")
        descriptions = {
            "new": "درخواست دریافت شد؛ هنوز پذیرش قرارداد نیست",
            "reviewing": "درخواست در حال بررسی کارشناسی است",
            "approved": "تأیید اولیه بررسی؛ نه قرارداد یا پرداخت",
            "closed": "پرونده بررسی بسته شده است",
        }
        response = render(request, "core/company_inquiry_receipt.html", {
            "status_text": descriptions.get(status, "وضعیت در حال بازبینی است"),
        })
        response["Cache-Control"] = "private, no-store, max-age=0"
        response["Referrer-Policy"] = "no-referrer"
        response["X-Robots-Tag"] = "noindex, nofollow"
        return response

    return _show(request, ticket)


def farm_economics_request(request):
    """Dedicated farm service intake using the SAME persisted company CRM."""
    if request.method == "POST":
        return company_portal_home(request, service="farm")
    if request.method != "GET":
        from django.http import HttpResponseNotAllowed
        return HttpResponseNotAllowed(["GET", "POST"])
    form = CompanyInquiryForm(initial={
        "kind": "commercial",
        "subject": "ZM-FARM | درخواست تحلیل اقتصادی مزرعه",
    })
    response = render(request, "core/farm_economics_request.html", {"form": form})
    response["Cache-Control"] = "no-store"
    response["Referrer-Policy"] = "no-referrer"
    return response
