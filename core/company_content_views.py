from datetime import timedelta
import re

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
    """Validate public inquiries before adding a sales lead to the CRM."""

    message = forms.CharField(max_length=5000, strip=True)
    privacy_consent = forms.BooleanField(
        required=True,
        label="I agree to processing for inquiry response and follow-up.",
    )
    # Invisible field never persisted to CRM.
    website = forms.CharField(required=False, max_length=128, widget=forms.HiddenInput)

    @staticmethod
    def _clean_customer_text(value, *, multiline=False):
        if not isinstance(value, str):
            raise forms.ValidationError("اطلاعات متنی نامعتبر است.")
        # Ignore harmless surrounding whitespace, preserve Persian letters.
        value = value.strip()
        if multiline:
            value = value.replace("\r\n", "\n").replace("\r", "\n")
        else:
            value = " ".join(value.split())
        for ch in value:
            code = ord(ch)
            if code < 32 and not (multiline and ch in ("\n", "\t")):
                raise forms.ValidationError("کاراکتر کنترلی نامعتبر است.")
            # Invisible overrides can reverse customer references and links.
            if code == 127 or 0x202A <= code <= 0x202E or 0x2066 <= code <= 0x2069:
                raise forms.ValidationError("کاراکتر کنترلی نامعتبر است.")
        return value

    def clean_website(self):
        if self.cleaned_data.get("website", "").strip():
            raise forms.ValidationError("درخواست نامعتبر است.")
        return ""

    def clean_name(self):
        value = self._clean_customer_text(self.cleaned_data["name"])
        if not value:
            raise forms.ValidationError("نام الزامی است.")
        return value

    def clean_organization(self):
        return self._clean_customer_text(self.cleaned_data.get("organization", ""))

    def clean_subject(self):
        value = self._clean_customer_text(self.cleaned_data["subject"])
        if not value:
            raise forms.ValidationError("موضوع درخواست الزامی است.")
        return value

    def clean_message(self):
        value = self._clean_customer_text(self.cleaned_data["message"], multiline=True)
        if not value:
            raise forms.ValidationError("شرح درخواست الزامی است.")
        return value

    def clean_email(self):
        email = self.cleaned_data["email"].strip()
        local, at, domain = email.rpartition("@")
        if not at or not local or not domain:
            raise forms.ValidationError("نشانی ایمیل نامعتبر است.")
        # Email local parts are not universally case-insensitive.
        return local + "@" + domain.lower()

    def clean_phone(self):
        phone = self._clean_customer_text(self.cleaned_data.get("phone", ""))
        if not phone:
            return ""
        if not re.fullmatch(r"\+?[\d\s().-]+", phone):
            raise forms.ValidationError("قالب شماره تلفن نامعتبر است.")
        count = sum(ch.isdigit() for ch in phone)
        if not 7 <= count <= 15:
            raise forms.ValidationError("طول شماره تلفن نامعتبر است.")
        return phone


    def clean(self):
        cleaned = super().clean()
        if cleaned.get("website"):
            raise forms.ValidationError("Invalid inquiry submission.")
        email, subject, message = (
            cleaned.get("email"), cleaned.get("subject"), cleaned.get("message")
        )
        if email and subject and message and CompanyInquiry.objects.filter(
            kind=cleaned.get("kind"),
            email=email,
            subject=subject,
            message=message,
            created_at__gte=timezone.now() - timedelta(minutes=3),
        ).exists():
            raise forms.ValidationError(
                "This exact inquiry has already been received recently."
            )
        return cleaned

    class Meta:
        model = CompanyInquiry
        fields = ("kind", "name", "organization", "email", "phone", "subject", "message")


def company_portal_home(request):
    from django.shortcuts import redirect
    from django.contrib import messages
    if request.method == "POST":
        try:
            declared = int(request.META.get("CONTENT_LENGTH", "0") or "0")
        except (ValueError, TypeError):
            declared = -1
        if declared < 0 or declared > 30000:
            messages.error(request, "حجم درخواست نامعتبر است؛ متن کوتاه‌تری وارد کنید.")
            return redirect("company")
        form = CompanyInquiryForm(request.POST)
        if form.is_valid():
            inquiry = form.save(commit=False)
            # Existing internal-only field: no schema or payment mutations.
            inquiry.internal_note = (
                "C19_PRIVACY_CONSENT_V1; purpose=inquiry_response_followup; "
                "source=company_web_form"
            )
            inquiry.save()
            messages.success(request, "درخواست در دفتر شرکت ثبت شد؛ بررسی و پاسخ پس از ارزیابی انجام می‌شود و پذیرش خدمت قطعی نیست.")
        else:
            messages.error(request, "درخواست ثبت نشد؛ اطلاعات، رضایت پردازش داده و تکراری نبودن پیام را بررسی کنید.")
        return redirect("company")
    return None
