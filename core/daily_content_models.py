from django.db import models

from .models import T, ResearchProject


class DailyContentPlan(T):
    """One daily two-article publication plan owned by the site's project."""

    project = models.ForeignKey(ResearchProject, on_delete=models.CASCADE, related_name="daily_content_plans")
    run_date = models.DateField()
    company_topic = models.CharField(max_length=300)
    ceo_topic = models.CharField(max_length=300)
    company_title = models.CharField(max_length=300, blank=True)
    ceo_title = models.CharField(max_length=300, blank=True)
    status = models.CharField(max_length=30, default="planned")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["project", "run_date"], name="unique_daily_content_plan_per_project_day")
        ]


class DailyContentDraft(T):
    """Draft article generated for a daily slot; publication is approval-gated."""

    PLAN_KINDS = (("company", "company"), ("ceo", "ceo"))
    plan = models.ForeignKey(DailyContentPlan, on_delete=models.CASCADE, related_name="drafts")
    kind = models.CharField(max_length=20, choices=PLAN_KINDS)
    title = models.CharField(max_length=300)
    slug = models.SlugField(unique=True)
    content = models.TextField()
    status = models.CharField(max_length=30, default="draft")
    knowledge_article = models.OneToOneField(
        "KnowledgeArticle", on_delete=models.PROTECT, null=True, blank=True, related_name="daily_content_draft"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["plan", "kind"], name="unique_daily_content_draft_kind")
        ]
