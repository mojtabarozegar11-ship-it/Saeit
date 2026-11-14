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
    """Consented first-party company inquiries, gated by canonical source."""

    message = forms.CharField(max_length=5000, min_length=20, strip=True)
    name = forms.CharField(max_length=200, min_length=2, strip=True)
    website = forms.CharField(required=False, max_length=120)
    consent = forms.BooleanField(required=True)

    class Meta:
        model = CompanyInquiry
        fields = ("kind", "name", "organization", "email", "phone",
                  "subject", "message")

    def clean_email(self):
        return self.cleaned_data["email"].strip().casefold()

    def clean_website(self):
        if self.cleaned_data["website"].strip():
            raise forms.ValidationError("درخواست قابل ثبت نیست.")
        return ""

    def clean_subject(self):
        value = self.cleaned_data["subject"].strip()
        if len(value) < 5:
            raise forms.ValidationError("موضوع معتبر لازم است.")
        return value

    def clean_name(self):
        value = self.cleaned_data["name"].strip()
        if len(value) < 2:
            raise forms.ValidationError("نام معتبر لازم است.")
        return value


COMPANY_LEGACY_SOURCE_MARKER = (
    "Source: company portal Django; consent: checked; "
    "nonbinding: true; automatic_contact: false."
)
COMPANY_MAX_POST_BYTES = 24_576
COMPANY_DUPLICATE_MINUTES = 15


def _company_response_headers(response):
    response["Cache-Control"] = "no-store, private, max-age=0"
    response["Pragma"] = "no-cache"
    response["X-Content-Type-Options"] = "nosniff"
    response["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    return response


def company_portal_home(request):
    """Handle POST; a disabled Django source NEVER stores a shadow lead."""
    from datetime import timedelta

    from django.conf import settings
    from django.contrib import messages
    from django.core.exceptions import DisallowedHost
    from django.db import transaction
    from django.http import HttpResponse, HttpResponseBadRequest
    from django.http.request import RawPostDataException
    from django.shortcuts import redirect
    from .service_intake_routing import (
        LEGACY_INQUIRY_PATH, django_service_intake_active,
    )

    if request.method != "POST":
        return None

    # No company customer information may cross into MojPlayWin tenant.
    try:
        host = request.get_host().split(":")[0].lower()
    except DisallowedHost:
        return _company_response_headers(HttpResponse(status=404))
    if host not in {"zomorodmelal.ir", "www.zomorodmelal.ir"} and not (
        settings.DEBUG and host in {"testserver", "localhost", "127.0.0.1"}
    ):
        return _company_response_headers(HttpResponse(status=404))

    # Legacy PHP is the default sole intake. Never forward a Django POST,
    # customer PII, request cookies or CSRF tokens to a second backend.
    if not django_service_intake_active():
        return _company_response_headers(HttpResponse(
            "ثبت درخواست در این مسیر فعلاً غیرفعال است. "
            f'<a href="{LEGACY_INQUIRY_PATH}">فرم اصلی درخواست همکاری</a>',
            status=503,
        ))

    length = request.META.get("CONTENT_LENGTH", "")
    if length not in ("", None):
        if not isinstance(length, str) or not length.isdecimal():
            return _company_response_headers(HttpResponseBadRequest("حجم درخواست نامعتبر است."))
        if int(length) > COMPANY_MAX_POST_BYTES:
            return _company_response_headers(HttpResponseBadRequest("حجم درخواست بیش از حد مجاز است."))
    try:
        if len(request.body) > COMPANY_MAX_POST_BYTES:
            return _company_response_headers(HttpResponseBadRequest("حجم درخواست بیش از حد مجاز است."))
    except RawPostDataException:
        return _company_response_headers(HttpResponseBadRequest("درخواست قابل بررسی نیست."))
    if request.content_type != "application/x-www-form-urlencoded" and request.content_type != "multipart/form-data":
        return _company_response_headers(HttpResponse(status=415))
    if request.FILES:
        return _company_response_headers(HttpResponseBadRequest("ضمیمه در این فرم پذیرفته نمی‌شود."))

    form = CompanyInquiryForm(request.POST)
    if not form.is_valid():
        messages.error(
            request, "درخواست معتبر نیست؛ اطلاعات الزامی و رضایت پردازش را بررسی کنید."
        )
        return _company_response_headers(redirect("company"))

    item = form.save(commit=False)
    now = timezone.now()
    # Scope deduplication by full request, not merely email or organization;
    # a changed customer question must remain eligible for a new inquiry.
    with transaction.atomic():
        exact_duplicate = CompanyInquiry.objects.select_for_update().filter(
            kind=item.kind,
            email__iexact=item.email,
            subject=item.subject,
            message=item.message,
            created_at__gte=now - timedelta(minutes=COMPANY_DUPLICATE_MINUTES),
            created_at__lte=now,
        ).exists()
        if not exact_duplicate:
            item.status = "new"
            item.internal_note = COMPANY_LEGACY_SOURCE_MARKER
            item.save()
    # Do not falsely say a duplicate caused another submission. Preserve the
    # customer's ability to change the question and submit a distinct inquiry.
    if exact_duplicate:
        messages.info(
            request,
            "درخواست یکسان قبلاً دریافت شده است؛ ثبت تکراری انجام نشد."
        )
    else:
        messages.success(
            request,
            "درخواست برای بررسی ثبت شد؛ این پیام تأیید سفارش یا قرارداد نیست."
        )
    return _company_response_headers(redirect("company"))
