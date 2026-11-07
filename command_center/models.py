"""Tenant-scoped editable MojPlayWin records. Published snapshots are immutable until reviewed."""
import re
from django.core.exceptions import ValidationError
from django.db import models

TENANT = "mojplaywin-main"
KINDS = [("content", "Page row/card"), ("offer", "Store offer"),
         ("job", "Production/editorial job"), ("agent_outcome", "Evidence-backed agent outcome")]
STATES = [("draft", "Draft"), ("review", "Quality review"),
          ("needs_revision", "Needs revision"), ("awaiting_approval", "Awaiting approval"),
          ("approved", "Approved"), ("published", "Published")]


def local_path(value, allow_empty=False):
    if allow_empty and not value:
        return True
    return bool(isinstance(value, str) and len(value) <= 200 and
                re.fullmatch(r"/(?!/)[a-zA-Z0-9_./-]*", value) and
                ".." not in value.split("/") and "\\" not in value)


class MpwRecord(models.Model):
    """Only the main domain may read/write these rows; not a shared-site CMS."""
    tenant = models.CharField(max_length=40, default=TENANT, editable=False, db_index=True)
    kind = models.CharField(max_length=20, choices=KINDS, db_index=True)
    key = models.SlugField(max_length=100, unique=True)
    page_path = models.CharField(max_length=200, default="/", db_index=True)
    title = models.CharField(max_length=200)
    draft = models.JSONField(default=dict)
    published_snapshot = models.JSONField(default=dict, blank=True)
    state = models.CharField(max_length=24, choices=STATES, default="draft")
    revision = models.PositiveIntegerField(default=1)
    quality_note = models.TextField(blank=True)
    quality_evidence = models.CharField(max_length=240, blank=True)
    approval_evidence = models.CharField(max_length=240, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("kind", "key")
        indexes = [models.Index(fields=("tenant", "kind", "page_path"), name="mpw_tenant_kind_page")]

    def clean(self):
        errors = {}
        if self.tenant != TENANT:
            errors["tenant"] = "Cross-tenant data is forbidden."
        if not local_path(self.page_path):
            errors["page_path"] = "Use an internal absolute site path."
        if not isinstance(self.draft, dict):
            errors["draft"] = "The editable source must be an object."
        if not isinstance(self.published_snapshot, dict):
            errors["published_snapshot"] = "Published source must be an object."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.kind}: {self.title} ({self.key})"


class WorkItem(models.Model):
    STATUS_CHOICES = (
        ("open", "باز"),
        ("in_progress", "در حال اجرا"),
        ("blocked", "متوقف"),
        ("done", "انجام‌شده"),
    )
    PRIORITY_CHOICES = (("low", "کم"), ("normal", "عادی"), ("high", "زیاد"), ("urgent", "فوری"))
    title = models.CharField(max_length=240)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="open", db_index=True)
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default="normal", db_index=True)
    assignee = models.ForeignKey("auth.User", null=True, blank=True, on_delete=models.PROTECT, related_name="desk_work_items")
    project = models.ForeignKey("core.ResearchProject", null=True, blank=True, on_delete=models.PROTECT, related_name="desk_work_items")
    resolution_reference = models.CharField(max_length=120, blank=True)
    created_by = models.ForeignKey("auth.User", on_delete=models.PROTECT, related_name="desk_created_work_items")
    due_at = models.DateTimeField(null=True, blank=True, db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    source_type = models.CharField(max_length=80, blank=True)
    source_id = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("status", "-priority", "due_at", "-created_at")
        indexes = [models.Index(fields=("status", "assignee"), name="desk_work_status_assignee")]

    def __str__(self):
        return self.title


class InternalMessage(models.Model):
    sender = models.ForeignKey("auth.User", on_delete=models.PROTECT, related_name="desk_sent_messages")
    recipient = models.ForeignKey("auth.User", on_delete=models.PROTECT, related_name="desk_received_messages")
    subject = models.CharField(max_length=240)
    body = models.TextField()
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("read_at", "-created_at")

    def __str__(self):
        return self.subject


class PrivateAuction(models.Model):
    STATUS_CHOICES = (("draft", "پیش‌نویس"), ("open", "باز"), ("closed", "بسته"), ("cancelled", "لغوشده"))
    title = models.CharField(max_length=240)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft", db_index=True)
    minimum_price = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey("auth.User", on_delete=models.PROTECT, related_name="desk_created_auctions")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("status", "-created_at")

    def __str__(self):
        return self.title


class CycleReport(models.Model):
    """Durable, staff-only result record for the C01-C50 operating ledger."""
    cycle = models.CharField(max_length=3, db_index=True)
    project_key = models.CharField(max_length=80, db_index=True)
    project_name = models.CharField(max_length=200)
    action = models.TextField()
    action_key = models.CharField(max_length=64)
    result = models.CharField(max_length=240)
    measure = models.CharField(max_length=160)
    blocker = models.CharField(max_length=240, blank=True)
    next_action = models.CharField(max_length=240)
    evidence = models.TextField()
    owner = models.CharField(max_length=160)
    action_date = models.DateField()
    readonly = models.BooleanField(default=False)
    created_by = models.ForeignKey("auth.User", on_delete=models.PROTECT, related_name="cycle_reports")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-action_date", "-created_at")
        constraints = [models.UniqueConstraint(fields=("cycle", "project_key", "action_key"), name="uniq_cycle_project_action")]


class CycleIssue(models.Model):
    CERTAINTY_CHOICES = (("unverified", "نیازمند تأیید"), ("verified", "تأییدشده"))
    STATUS_CHOICES = (("open", "باز"), ("resolved", "رفع‌شده"))
    cycle = models.CharField(max_length=3, db_index=True)
    project_key = models.CharField(max_length=80, db_index=True)
    title = models.TextField()
    owner = models.CharField(max_length=160)
    observed_on = models.DateField()
    certainty = models.CharField(max_length=12, choices=CERTAINTY_CHOICES, default="unverified")
    source = models.TextField(blank=True)
    next_action = models.CharField(max_length=240)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="open", db_index=True)
    resolution_evidence = models.TextField(blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey("auth.User", on_delete=models.PROTECT, related_name="cycle_issues")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("status", "-created_at")


class ApprovalDecision(models.Model):
    KIND_CHOICES = (("email", "ارسال ایمیل"), ("deploy", "استقرار و انتشار"), ("cost", "هزینه یا تعهد مالی"))
    STATUS_CHOICES = (("approved", "تأیید شد"), ("rejected", "رد شد"))
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, db_index=True)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES)
    approver = models.CharField(max_length=160)
    evidence = models.TextField(blank=True)
    created_by = models.ForeignKey("auth.User", on_delete=models.PROTECT, related_name="approval_decisions")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
