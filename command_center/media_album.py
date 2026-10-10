"""Private content-agent image album backed by existing CompanyGalleryMedia."""
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.core.exceptions import ValidationError
from django.core.files.images import get_image_dimensions
from core.models import CompanyGalleryMedia

MAX_IMAGE_BYTES = 5 * 1024 * 1024
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}

@staff_member_required
@require_http_methods(["GET", "POST"])
def album(request):
    if request.method == "GET":
        rows = CompanyGalleryMedia.objects.filter(media_type="image").order_by("-created_at")[:100]
        items = [{
            "id": row.pk, "title": row.title, "topic": row.project_label,
            "description": row.description, "tags": row.tags,
            "image_url": row.image.url if row.image else None,
            "approved_for_publication": row.published,
        } for row in rows]
        response = JsonResponse({"items": items, "read_only_for_agents": True})
    else:
        image = request.FILES.get("image")
        title = request.POST.get("title", "").strip()
        topic = request.POST.get("topic", "").strip()
        description = request.POST.get("description", "").strip()
        tags = [x.strip() for x in request.POST.get("tags", "").split(",") if x.strip()]
        if not image or not title or not topic or len(title) > 300 or len(topic) > 200 or len(description) > 2000 or len(tags) > 20:
            return JsonResponse({"error": "invalid_metadata"}, status=400)
        if image.size > MAX_IMAGE_BYTES or image.content_type not in ALLOWED_TYPES:
            return JsonResponse({"error": "unsupported_image"}, status=400)
        try:
            width, height = get_image_dimensions(image)
            if not width or not height or width * height > 30_000_000:
                raise ValidationError("Invalid dimensions")
            image.seek(0)
        except (ValueError, OSError, ValidationError):
            return JsonResponse({"error": "invalid_image"}, status=400)
        item = CompanyGalleryMedia(
            media_type="image", title=title, project_label=topic,
            description=description, tags=tags, image=image, published=False,
        )
        item.full_clean()
        item.save()
        response = JsonResponse({"id": item.pk, "status": "private", "approved_for_publication": False}, status=201)
    response["Cache-Control"] = "no-store"
    return response
