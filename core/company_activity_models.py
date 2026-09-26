from django.db import models


class CompanyActivityAgentPlan(models.Model):
    code = models.SlugField(unique=True)
    title = models.CharField(max_length=300)
    mission = models.TextField()
    cadence_hours = models.PositiveIntegerField(default=24)
    reports_per_day = models.PositiveIntegerField(default=6)
    active = models.BooleanField(default=True)
    require_owner_approval = models.BooleanField(default=True)
    last_run_at = models.DateTimeField(null=True, blank=True)
    next_run_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class CompanyActivityReport(models.Model):
    STATUS = (("draft", "Draft"), ("review", "Review"), ("approved", "Approved"), ("published", "Published"), ("blocked", "Blocked"))
    REPORT_TYPES = (("DAILY_DIGEST", "Daily Digest"), ("ACTIVITY_ANALYSIS", "Activity Analysis"), ("TREND_ANALYSIS", "Trend Analysis"), ("UNIT_ANALYSIS", "Unit Analysis"), ("PROJECT_ANALYSIS", "Project Analysis"), ("EXECUTIVE_BRIEF", "Executive Brief"))
    plan = models.ForeignKey(CompanyActivityAgentPlan, on_delete=models.CASCADE, related_name="reports")
    report_type = models.CharField(max_length=40, choices=REPORT_TYPES)
    title = models.CharField(max_length=400)
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    source_activity_ids = models.JSONField(default=list)
    source_count = models.PositiveIntegerField(default=0)
    content = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS, default="draft")
    approval_required = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["plan", "report_type", "period_start"], name="unique_company_activity_daily_report")]
        indexes = [models.Index(fields=["report_type", "period_end"]), models.Index(fields=["status", "created_at"])]
