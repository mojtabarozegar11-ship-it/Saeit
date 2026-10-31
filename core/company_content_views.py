from urllib.parse import unquote, urlsplit
from django.db import DatabaseError
from django.db.models import Q
from django.http import Http404, HttpResponse
from django.shortcuts import render
from django.utils import timezone
from .company_content_models import CompanyContentLink, CompanyGalleryMedia
from .newsletter_models import NewsletterStory
from .company_inquiry_models import CompanyInquiry
from .public_catalog_guard import missing_public_tables, mark_public_data_unavailable


def safe_gallery_target_path(path):
    """Reject disguised network-path and traversal links; keep safe local URLs."""
    if not isinstance(path, str) or not path.startswith("/") or path.startswith("//"):
        return ""
    if "\\" in path or any(ord(ch) < 32 or ord(ch) == 127 for ch in path):
        return ""
    try:
        parsed = urlsplit(path)
        if parsed.scheme or parsed.netloc or not parsed.path.startswith("/"):
            return ""
        decoded = parsed.path
        # Multiple URL decoding stages can turn /%252fhost into //host.
        # Fail closed without changing the displayed gallery or the stored URL.
        for _ in range(8):
            # Invalid UTF-8 percent escapes must not silently become U+FFFD
            # and produce a misleading public gallery target.
            decoded_next = unquote(decoded, errors="strict")
            if decoded_next == decoded:
                break
            decoded = decoded_next
            if decoded.startswith("//") or "\\" in decoded:
                return ""
            # A proxy that decodes an encoded '?' or '#' in the PATH can
            # reinterpret it as query/fragment syntax; fail closed rather
            # than redirecting users to an ambiguous gallery destination.
            if "?" in decoded or "#" in decoded:
                return ""
            if any(ord(ch) < 32 or ord(ch) == 127 for ch in decoded):
                return ""
        else:
            # Do not accept arbitrarily nested percent encoding: a downstream
            # proxy could decode more layers than this application inspected.
            return ""
        if decoded.startswith("//") or any(segment in (".", "..") for segment in decoded.split("/")):
            return ""
    except (ValueError, UnicodeDecodeError):
        return ""
    return path


def _company_gallery_with_schema(request):
    catalog_unavailable = missing_public_tables(CompanyGalleryMedia, NewsletterStory)
    kind = request.GET.get("type", "").strip().lower()[:16]  # Bound public filter parsing
    query = request.GET.get("q", "").strip()[:120]  # Avoid unbounded public title scans
    media = []
    if not catalog_unavailable:
        now = timezone.now()
        # A published gallery item must not reveal media attached to an
        # embargoed/draft newsletter story. Standalone media remains visible.
        media = CompanyGalleryMedia.objects.filter(
            published=True, published_at__lte=now
        ).filter(
            Q(newsletter_story__isnull=True) |
            Q(newsletter_story__status="published", newsletter_story__published_at__lte=now)
        ).select_related("newsletter_story")
        if kind in {"image", "video"}:
            media = media.filter(media_type=kind)
        if query:
            media = media.filter(title__icontains=query)
        # Stable newest-first pagination: unordered slices can reshuffle
        # published media between requests and hide recently approved work.
        media = list(media.order_by("-published_at", "-pk")[:100])
        for item in media:
            item.safe_target_path = safe_gallery_target_path(item.target_path)
    response = render(request, "core/company_gallery.html", {
        "media": media, "query": query, "kind": kind,
        "catalog_temporarily_unavailable": catalog_unavailable,
    })
    return mark_public_data_unavailable(response) if catalog_unavailable else response



def company_gallery(request):
    """Do not turn a mid-query/gallery-render DB outage into an HTTP 500."""
    try:
        return _company_gallery_with_schema(request)
    except DatabaseError:
        response = HttpResponse(
            '<!doctype html><html lang="fa" dir="rtl"><head>'
            '<meta charset="utf-8"><title>گالری موقتاً در دسترس نیست</title>'
            '</head><body><main><h1>گالری موقتاً در دسترس نیست</h1>'
            '<p role="status">نمایش تصاویر و ویدئوها موقتاً امکان‌پذیر نیست؛ '
            'این وضعیت به معنای حذف آثار نیست.</p>'
            '<p><a href="/company/">بازگشت به شرکت</a></p>'
            '</main></body></html>',
            status=503, content_type="text/html; charset=utf-8",
        )
        response["Retry-After"] = "300"
        return mark_public_data_unavailable(response)


def _company_temporarily_unavailable():
    """Fail truthfully without echoing submitted contact information."""
    response = HttpResponse(
        '<!doctype html><html lang="fa" dir="rtl"><head>'
        '<meta charset="utf-8"><title>سامانه موقتاً در دسترس نیست</title>'
        '</head><body><main><h1>سامانه موقتاً در دسترس نیست</h1>'
        '<p role="status">وضعیت ثبت درخواست قابل تأیید نیست؛ پیش از ارسال دوباره با شرکت تماس بگیرید.</p>'
        '<p><a href="/company/">بازگشت به شرکت</a></p>'
        '</main></body></html>',
        status=503,
        content_type="text/html; charset=utf-8",
    )
    response["Retry-After"] = "300"
    return mark_public_data_unavailable(response)


def _company_content_feed_with_schema(request, slug):
    knowledge_model = CompanyContentLink._meta.get_field("knowledge_article").remote_field.model
    if missing_public_tables(CompanyContentLink, NewsletterStory, knowledge_model):
        return _company_temporarily_unavailable()
    target = f"/company/{slug.strip('/')}/" if slug != "company" else "/company/"
    links = CompanyContentLink.objects.filter(target_path=target).select_related("newsletter_story", "knowledge_article")
    # A published editorial state does not override a future publication embargo.
    # Company feeds must use the same visibility boundary as newsletter detail.
    now = timezone.now()
    links = [
        x for x in links
        if (
            x.content_type == "newsletter"
            and x.newsletter_story
            and x.newsletter_story.status == "published"
            and x.newsletter_story.published_at is not None
            and x.newsletter_story.published_at <= now
        ) or (
            x.content_type == "knowledge"
            and x.knowledge_article
            and x.knowledge_article.published
        )
    ]
    if not links:
        raise Http404("Company content feed not found")
    return render(request, "core/company_content_feed.html", {"target": target, "links": links})


def company_content_feed(request, slug):
    """Handle database loss after schema introspection without a public 500."""
    try:
        return _company_content_feed_with_schema(request, slug)
    except DatabaseError:
        return _company_temporarily_unavailable()


def company_portal_home(request):
    from django.shortcuts import redirect
    from django.contrib import messages
    if request.method == "POST":
        required = ["kind", "name", "email", "subject", "message"]
        if all(request.POST.get(x, "").strip() for x in required):
            if missing_public_tables(CompanyInquiry):
                return _company_temporarily_unavailable()
            # Validate model choices, email format and database field lengths
            # before any insert. Invalid user input must not become a 500 or
            # a false confirmation, and must not be copied into public logs.
            from django.core.exceptions import ValidationError
            fields = {
                "kind": request.POST["kind"].strip(), "name": request.POST["name"].strip(),
                "organization": request.POST.get("organization", "").strip(),
                "email": request.POST["email"].strip(),
                "phone": request.POST.get("phone", "").strip(),
                "subject": request.POST["subject"].strip(),
                "message": request.POST["message"].strip(),
            }
            try:
                CompanyInquiry(**fields).full_clean(validate_unique=False, validate_constraints=False)
            except ValidationError:
                messages.error(request, "اطلاعات درخواست معتبر نیست؛ لطفاً فیلدها را اصلاح کنید.")
                return redirect("company")
            except DatabaseError:
                return _company_temporarily_unavailable()
            # A transport failure after an INSERT may leave the commit outcome
            # uncertain. Never claim failure/success or invite blind resubmits.
            try:
                CompanyInquiry.objects.create(**fields)
            except DatabaseError:
                return _company_temporarily_unavailable()
            messages.success(request, "درخواست شما با موفقیت ثبت شد و برای بررسی کارشناسی ارسال گردید.")
        else:
            messages.error(request, "لطفاً تمام فیلدهای الزامی را تکمیل کنید.")
        return redirect("company")
    return None
