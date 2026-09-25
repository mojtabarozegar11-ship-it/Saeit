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


def company_portal_home(request):
    from django.shortcuts import redirect
    from django.contrib import messages
    if request.method == "POST":
        required = ["kind", "name", "email", "subject", "message"]
        if all(request.POST.get(x, "").strip() for x in required):
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
