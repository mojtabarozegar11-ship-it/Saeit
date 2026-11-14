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


from .company_sales_intake import (
    CompanySalesInquiryForm as CompanyInquiryForm,
    require_company_host, save_inbound_inquiry, validate_body_size,
)
from django.views.decorators.csrf import csrf_protect
from django.http import HttpResponse


@csrf_protect
def company_portal_home(request):
    """Share the same consent and anti-abuse contract as native /contact/."""
    from django.contrib import messages
    from django.shortcuts import redirect
    require_company_host(request)
    if request.method != "POST":
        return redirect("company")
    try:
        validate_body_size(request)
    except forms.ValidationError:
        return HttpResponse("درخواست بیش از حد مجاز است.", status=413)
    form = CompanyInquiryForm(request.POST)
    if not form.is_valid():
        response = render(request, "core/company_contact.html", {
            "form": form, "inquiry_received": False,
        }, status=422)
        response["Cache-Control"] = "private, no-store, max-age=0"
        response["X-Robots-Tag"] = "noindex, nofollow"
        return response
    save_inbound_inquiry(form)
    messages.success(
        request,
        "درخواست برای بررسی داخلی ثبت شد. این ثبت، تأیید قرارداد یا پرداخت نیست.",
    )
    return redirect("company")
