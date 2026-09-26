import hashlib
import re
from datetime import date

from django.utils.text import slugify

from .models import Agent, NewsletterSchedule, NewsletterSource, NewsletterStory


def fingerprint(*parts):
    raw = "|".join(re.sub(r"\\s+", " ", str(p or "")).strip().lower() for p in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def create_draft(*, agent_code, story_type, title, summary, body, source=None, event_date=None, keywords=None, publish_at=None):
    agent = Agent.objects.get(code=agent_code, active=True)
    source_fingerprint = fingerprint(source.url) if source else ""
    fp = fingerprint(story_type, title, source_fingerprint, event_date or "")
    if NewsletterStory.objects.filter(fingerprint=fp).exists():
        return None, "duplicate"
    base = slugify(title, allow_unicode=True)[:150] or fp[:12]
    slug = base
    n = 2
    while NewsletterStory.objects.filter(slug=slug).exists():
        slug = f"{base}-{n}"; n += 1
    story = NewsletterStory.objects.create(
        agent=agent, source=source, story_type=story_type, title=title.strip(),
        slug=slug, summary=summary.strip(), body=body.strip(), event_date=event_date,
        fingerprint=fp, source_fingerprint=source_fingerprint,
        seo_keywords=keywords or [], published_at=publish_at, status="scheduled" if publish_at else "draft",
    )
    if story.status == "draft":
        from .blog_distribution import queue_story_distribution
        queue_story_distribution(story)
    return story, "created"


def process_submission(submission):
    """Turn an owner/admin submission into an agent-owned draft; publishing remains approval-gated."""
    from django.utils import timezone
    if submission.status not in ("queued", "processing"):
        return submission.generated_story
    submission.status = "processing"
    submission.save(update_fields=["status"])

    agent = Agent.objects.filter(code="content-director", active=True).first()
    if not agent:
        submission.status = "rejected"
        submission.processed_at = timezone.now()
        submission.save(update_fields=["status", "processed_at"])
        return None

    story, reason = create_draft(
        agent_code="content-director",
        story_type="company",
        title=submission.subject,
        summary=submission.body[:500],
        body=submission.body,
        keywords=[submission.subject, "شرکت کشت و صنعت زمرد ملل", "مجتبی روزگار", "محقق و پژوهشگر"],
        publish_at=submission.requested_publish_at,
    )
    if story:
        unit_title = submission.company_unit_title.strip() or f"واحد تحقیق و توسعه · {submission.subject.strip()}"
        unit_slug = submission.company_unit_slug.strip() or slugify(unit_title, allow_unicode=True)[:170]
        story.author_name = "مجتبی روزگار"
        story.company_activity_kind = "activity"
        story.company_unit_title = unit_title
        story.company_unit_slug = unit_slug
        story.company_activity_status = submission.company_activity_status.strip() or "پژوهش"
        story.company_project_title = submission.company_project_title.strip()
        story.company_activity_content = submission.body.strip()
        story.manager_action = "محتوای ورودی از پنل مدیریت؛ محدود به فعالیت‌های واقعی شرکت. پرونده فعالیت شرکت نیز از همین خبر ساخته می‌شود."
        story.save(update_fields=["author_name", "company_activity_kind", "company_unit_title", "company_unit_slug", "company_activity_status", "company_project_title", "company_activity_content", "manager_action", "updated_at"])
    if story is None:
        submission.status = "rejected"
        submission.processed_at = timezone.now()
        submission.save(update_fields=["status", "processed_at"])
        return None

    if submission.image:
        story.image.name = submission.image.name
    if submission.video:
        story.video.name = submission.video.name
    story.save(update_fields=["image", "video", "updated_at"])

    from .company_content_models import CompanyContentLink
    activity_path = f"/company/activity-{story.pk}/"
    target_paths = [activity_path]
    target_paths.extend([p.strip() for p in re.split(r"[\n,]+", submission.company_target_paths or "") if p.strip()])
    target_paths = [p for p in target_paths if p.startswith("/company/")]
    for target_path in dict.fromkeys(target_paths):
        CompanyContentLink.objects.get_or_create(
            content_type="newsletter", newsletter_story=story, target_path=target_path,
            defaults={"relation": "primary" if target_path == target_paths[0] else "related"},
        )

    submission.status = "drafted"
    submission.processed_at = timezone.now()
    submission.generated_story = story
    submission.save(update_fields=["status", "processed_at", "generated_story"])
    return story


def daily_quota_snapshot(day=None):
    day = day or date.today()
    schedule = NewsletterSchedule.objects.filter(active=True).first()
    if not schedule:
        return {"date": day.isoformat(), "configured": False}
    counts = {}
    elapsed = (day - schedule.start_date).days
    pattern = schedule.company_daily_pattern or []
    company_limit = pattern[elapsed % len(pattern)] if pattern else schedule.company_news_daily
    for key, limit in (("company", company_limit), ("world", schedule.world_news_daily), ("report", schedule.reports_daily)):
        counts[key] = {"target": limit, "published": NewsletterStory.objects.filter(story_type=key, status="published", published_at__date=day).count()}
        counts[key]["remaining"] = max(0, limit - counts[key]["published"])
    return {"date": day.isoformat(), "configured": True, "approval_required": schedule.publication_requires_approval, "counts": counts}


def register_source(*, publisher, title, url, kind="world"):
    source, created = NewsletterSource.objects.get_or_create(
        url=url, defaults={"publisher": publisher, "title": title, "kind": kind}
    )
    return source, created
