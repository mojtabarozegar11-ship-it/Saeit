"""Read-only album suggestions for existing newsletter stories."""
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET
from core.models import NewsletterStory
from .media_matching import recommend_images

@staff_member_required
@require_GET
def suggestions(request, story_id):
    story = get_object_or_404(NewsletterStory, pk=story_id)
    terms = [story.title] + [x for x in story.seo_keywords if isinstance(x, str)]
    matches = {}
    for term in terms[:6]:
        for image in recommend_images(term, limit=10):
            matches.setdefault(image["asset_id"], image)
        if len(matches) >= 20:
            break
    response = JsonResponse({
        "story_id": story.pk,
        "suggestions": list(matches.values())[:20],
        "applied": False,
        "publication_requires_owner_approval": True,
    })
    response["Cache-Control"] = "no-store"
    return response
