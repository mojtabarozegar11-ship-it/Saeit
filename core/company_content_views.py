from django import forms
from datetime import timedelta
import re

from django.utils import timezone
from django.http import Http404
from django.shortcuts import render
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
    """Accept qualified, privacy-conscious customer leads, not arbitrary text."""

    # A non-visible honeypot protects the existing customer form without
    # introducing a CAPTCHA, paid API or a second bot.
    website = forms.CharField(required=False, max_length=128)
    message = forms.CharField(max_length=5000, strip=True)

    class Meta:
        model = CompanyInquiry
        fields = ("kind", "name", "organization", "email", "phone", "subject", "message")

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


def company_portal_home(request):
    from django.shortcuts import redirect
    from django.contrib import messages

    if request.method == "POST":
        # Defensive bound before attempting to parse a large attacker payload.
        # CSRF middleware can consume the POST stream before this view.
        # Check declared content length rather than re-reading request.body.
        try:
            declared_length = int(request.META.get("CONTENT_LENGTH") or 0)
        except (ValueError, TypeError):
            declared_length = 0
        if declared_length > 12000:
            from django.http import HttpResponse
            return HttpResponse("Request too large", status=413,
                                content_type="text/plain; charset=utf-8")
        form = CompanyInquiryForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            # Sequential double-clicks/refreshes must not inflate the CRM.
            # Database is the source of truth; no cache or paid service needed.
            recent = CompanyInquiry.objects.filter(
                kind=data["kind"], email=data["email"],
                subject=data["subject"], message=data["message"],
                created_at__gte=timezone.now() - timedelta(minutes=3),
            ).exists()
            if recent:
                messages.info(request, "درخواست یکسان قبلاً ثبت شده است؛ لطفاً از ثبت تکراری خودداری کنید.")
            else:
                form.save()
                messages.success(request, "درخواست شما ثبت شد و در صف بررسی شرکت قرار گرفت.")
        else:
            messages.error(request, "اطلاعات درخواست معتبر نیست؛ نام، نوع همکاری، ایمیل، موضوع و شرح درخواست را بررسی کنید.")
        # Keep user at the enquiry block so errors and success are visible.
        from django.urls import reverse
        return redirect(reverse("company") + "#company-request")
    return None
