from django.http import Http404, HttpResponse
from django.shortcuts import render
from django.utils import timezone
from .company_content_models import CompanyContentLink, CompanyGalleryMedia
from .newsletter_models import NewsletterStory
from .company_inquiry_models import CompanyInquiry
from .public_catalog_guard import missing_public_tables, mark_public_data_unavailable


def company_gallery(request):
    catalog_unavailable = missing_public_tables(CompanyGalleryMedia, NewsletterStory)
    kind = request.GET.get("type", "").strip().lower()
    query = request.GET.get("q", "").strip()
    media = []
    if not catalog_unavailable:
        media = CompanyGalleryMedia.objects.filter(
            published=True, published_at__lte=timezone.now()
        ).select_related("newsletter_story")
        if kind in {"image", "video"}:
            media = media.filter(media_type=kind)
        if query:
            media = media.filter(title__icontains=query)
        media = media[:100]
    response = render(request, "core/company_gallery.html", {
        "media": media, "query": query, "kind": kind,
        "catalog_temporarily_unavailable": catalog_unavailable,
    })
    return mark_public_data_unavailable(response) if catalog_unavailable else response



def _company_temporarily_unavailable():
    """Fail truthfully without echoing submitted contact information."""
    response = HttpResponse(
        '<!doctype html><html lang="fa" dir="rtl"><head>'
        '<meta charset="utf-8"><title>سامانه موقتاً در دسترس نیست</title>'
        '</head><body><main><h1>سامانه موقتاً در دسترس نیست</h1>'
        '<p role="status">درخواست شما ثبت نشده است؛ لطفاً بعداً دوباره تلاش کنید.</p>'
        '<p><a href="/company/">بازگشت به شرکت</a></p>'
        '</main></body></html>',
        status=503,
        content_type="text/html; charset=utf-8",
    )
    response["Retry-After"] = "300"
    return mark_public_data_unavailable(response)


def company_content_feed(request, slug):
    knowledge_model = CompanyContentLink._meta.get_field("knowledge_article").remote_field.model
    if missing_public_tables(CompanyContentLink, NewsletterStory, knowledge_model):
        return _company_temporarily_unavailable()
    target = f"/company/{slug.strip('/')}/" if slug != "company" else "/company/"
    links = CompanyContentLink.objects.filter(target_path=target).select_related("newsletter_story", "knowledge_article")
    links = [x for x in links if (x.newsletter_story and x.newsletter_story.status == "published") or (x.knowledge_article and x.knowledge_article.published)]
    if not links:
        raise Http404("Company content feed not found")
    return render(request, "core/company_content_feed.html", {"target": target, "links": links})


def company_portal_home(request):
    from django.shortcuts import redirect
    from django.contrib import messages
    if request.method == "POST":
        required = ["kind", "name", "email", "subject", "message"]
        if all(request.POST.get(x, "").strip() for x in required):
            if missing_public_tables(CompanyInquiry):
                return _company_temporarily_unavailable()
            CompanyInquiry.objects.create(
                kind=request.POST["kind"].strip(), name=request.POST["name"].strip(),
                organization=request.POST.get("organization", "").strip(), email=request.POST["email"].strip(),
                phone=request.POST.get("phone", "").strip(), subject=request.POST["subject"].strip(),
                message=request.POST["message"].strip(),
            )
            messages.success(request, "درخواست شما با موفقیت ثبت شد و برای بررسی کارشناسی ارسال گردید.")
        else:
            messages.error(request, "لطفاً تمام فیلدهای الزامی را تکمیل کنید.")
        return redirect("company")
    return None
