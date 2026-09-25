from django.shortcuts import render

from .models import BlogPage, ExternalBlogTarget, NewsletterStory


def blog_home(request):
    pages = BlogPage.objects.filter(active=True).order_by("seo_priority", "code")
    stories = NewsletterStory.objects.filter(status="published").order_by("-published_at")[:30]
    targets = ExternalBlogTarget.objects.all().order_by("code")
    return render(request, "core/blog.html", {"pages": pages, "stories": stories, "targets": targets})


def blog_page(request, slug):
    page = BlogPage.objects.filter(active=True).filter(slug=slug).first() or BlogPage.objects.filter(active=True, code=slug).first()
    if page is None:
        from django.http import Http404
        raise Http404("Blog page not found")
    stories = NewsletterStory.objects.filter(status="published", blog_publications__internal_page=page).distinct().order_by("-published_at")
    translations = page.translations.all().order_by("language")
    return render(request, "core/blog_page.html", {"page": page, "stories": stories, "translations": translations})
