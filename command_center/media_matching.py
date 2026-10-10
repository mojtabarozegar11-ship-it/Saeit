"""Reusable topic-based asset recommendations for editorial agents.

Recommendations never publish, copy, or attach media automatically.
"""
from django.db.models import Q
from core.models import CompanyGalleryMedia


def recommend_images(topic, *, limit=10):
    topic = (topic or "").strip()
    if not topic:
        return []
    limit = max(1, min(int(limit), 20))
    matches = CompanyGalleryMedia.objects.filter(
        media_type="image",
    ).exclude(image="").filter(
        Q(project_label__icontains=topic)
        | Q(title__icontains=topic)
        | Q(description__icontains=topic)
    ).order_by("-created_at")[:limit]
    return [
        {
            "asset_id": media.pk,
            "title": media.title,
            "topic": media.project_label,
            "tags": media.tags,
            "usable_in_draft": True,
            "publication_requires_approval": True,
            "published": bool(media.published),
        }
        for media in matches
    ]
