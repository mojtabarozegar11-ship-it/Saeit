"""Metadata-only image lookup for content agents; no publication permission."""
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.db.models import Q
from core.models import CompanyGalleryMedia

@staff_member_required
@require_GET
def search(request):
    topic = request.GET.get("topic", "").strip()[:120]
    if not topic:
        return JsonResponse({"error": "topic_required"}, status=400)
    matches = CompanyGalleryMedia.objects.filter(
        media_type="image", image__isnull=False
    ).filter(Q(project_label__icontains=topic) | Q(title__icontains=topic) |
             Q(description__icontains=topic)).order_by("-created_at")[:30]
    response = JsonResponse({
        "topic": topic,
        "assets": [{
            "id": row.pk, "title": row.title, "topic": row.project_label,
            "tags": row.tags, "description": row.description,
            "image_url": row.image.url if row.published else None,
            "publication_authorized": bool(row.published),
        } for row in matches],
        "requires_owner_approval_to_publish": True,
    })
    response["Cache-Control"] = "no-store"
    return response
