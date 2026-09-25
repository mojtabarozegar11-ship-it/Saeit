from .models import BlogDistributionPlan, BlogPage, BlogPublication, ExternalBlogTarget, NewsletterStory


def queue_story_distribution(story):
    plan, _ = BlogDistributionPlan.objects.get_or_create(story=story, defaults={"internal_count": 50, "external_count": 10, "languages": ["fa", "en", "ar", "es", "fr", "de", "zh", "ru", "tr", "it"], "requires_owner_approval": True})
    pages = list(BlogPage.objects.filter(active=True).order_by("seo_priority", "code")[:50])
    targets = list(ExternalBlogTarget.objects.filter(active=True, authorized=True).order_by("code")[:10])
    for page in pages:
        BlogPublication.objects.get_or_create(story=story, internal_page=page, language=page.language, defaults={"status": "queued"})
    for target in targets:
        BlogPublication.objects.get_or_create(story=story, external_target=target, language=target.language, defaults={"status": "blocked"})
    return plan, len(pages), len(targets)


def publication_readiness(story):
    plan = getattr(story, "distribution_plan", None)
    if not plan:
        return {"ready": False, "reason": "distribution_plan_missing"}
    internal = story.blog_publications.filter(internal_page__isnull=False, status="queued").count()
    external = story.blog_publications.filter(external_target__isnull=False, status="queued").count()
    return {"ready": plan.requires_owner_approval is False and internal == 50 and external == 10, "internal_queued": internal, "external_queued": external, "approval_required": plan.requires_owner_approval}
