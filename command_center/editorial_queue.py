"""Read-only editorial queue using existing newsletter records."""
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from core.models import NewsletterStory

@staff_member_required
@require_GET
def queue(request):
    allowed = ("draft", "approved", "scheduled")
    rows = list(NewsletterStory.objects.filter(status__in=allowed)
        .order_by("-created_at").values(
            "id", "title", "slug", "story_type", "status", "created_at"
        )[:100])
    response = JsonResponse({
        "items": rows,
        "truncated": NewsletterStory.objects.filter(status__in=allowed).count() > 100,
        "read_only": True,
    })
    response["Cache-Control"] = "no-store"
    return response
