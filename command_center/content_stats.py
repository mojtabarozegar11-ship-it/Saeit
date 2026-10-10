"""Read-only editorial statistics from existing Django content records."""
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from core.models import BlogPage, NewsletterStory, NewsletterPublication

@staff_member_required
@require_GET
def stats(request):
    result = {
        "blog_pages": BlogPage.objects.count(),
        "active_blog_pages": BlogPage.objects.filter(active=True).count(),
        "stories": NewsletterStory.objects.count(),
        "published_stories": NewsletterStory.objects.filter(status="published").count(),
        "publications": NewsletterPublication.objects.count(),
        "live_publishing_connected": False,
    }
    response = JsonResponse(result)
    response["Cache-Control"] = "no-store"
    return response
