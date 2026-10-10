"""Staff-only editorial detail; no publishing or mutation."""
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET
from core.models import NewsletterStory

@staff_member_required
@require_GET
def detail(request, story_id):
    story = get_object_or_404(NewsletterStory, pk=story_id)
    response = JsonResponse({
        "id": story.pk,
        "title": story.title,
        "slug": story.slug,
        "summary": story.summary,
        "body": story.body,
        "status": story.status,
        "story_type": story.story_type,
        "seo_keywords": story.seo_keywords,
        "image_url": story.image.url if story.image else None,
        "video_url": story.video.url if story.video else None,
        "read_only": True,
    })
    response["Cache-Control"] = "no-store"
    return response
