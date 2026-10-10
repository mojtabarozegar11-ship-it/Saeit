"""Staff-only image recommendations for editorial planning."""
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from .media_matching import recommend_images

@staff_member_required
@require_GET
def search(request):
    topic = request.GET.get("topic", "").strip()[:120]
    if not topic:
        return JsonResponse({"error": "topic_required"}, status=400)
    response = JsonResponse({
        "topic": topic,
        "assets": recommend_images(topic, limit=20),
        "requires_owner_approval_to_publish": True,
    })
    response["Cache-Control"] = "no-store"
    return response
