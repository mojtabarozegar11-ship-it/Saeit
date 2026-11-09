"""Public, approval-gated company and agricultural world-news listing.

RSS ingestion never writes directly to this public surface. Only previously
published, signed stories that survive the shared editorial exclusion gate
can be linked here.
"""

from django.db.models import Q
from django.shortcuts import render
from django.utils import timezone

from .editorial_policy import visible_news_stories
from .editorial_signature import has_final_signature
from .models import NewsletterStory


def news_home(request):
    eligible = NewsletterStory.objects.filter(
        status="published",
        published_at__lte=timezone.now(),
        story_type__in=("company", "world"),
    ).filter(Q(story_type="company") | Q(story_type="world", source__isnull=False))
    reviewed = visible_news_stories(eligible, limit=60)
    stories = [story for story in reviewed if has_final_signature(story.body)][:48]
    return render(request, "core/news.html", {"stories": stories})
