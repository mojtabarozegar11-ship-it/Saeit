from django.db import models
from django.utils import timezone


class KnowledgeAgentPlan(models.Model):
    START_DATE = timezone.datetime(2019, 11, 16).date()
    code = models.SlugField(unique=True)
    title = models.CharField(max_length=300)
    mission = models.TextField()
    goal = models.TextField()
    public_free = models.BooleanField(default=True)
    seo_first = models.BooleanField(default=True)
    audience_goal = models.TextField(default="جذب مخاطب عمومی از جست‌وجو و تبدیل سایت به مرجع رایگان و قابل استناد.")
    start_date = models.DateField(default=START_DATE)
    cadence_hours = models.PositiveIntegerField(default=24)
    active = models.BooleanField(default=True)
    require_owner_approval = models.BooleanField(default=True)
    last_run_at = models.DateTimeField(null=True, blank=True)
    next_run_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class KnowledgeDomain(models.Model):
    code = models.SlugField(unique=True)
    title = models.CharField(max_length=300)
    scientific_scope = models.TextField()
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="children")
    priority = models.PositiveIntegerField(default=100)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class KnowledgeBook(models.Model):
    STATUS = (("planned", "Planned"), ("drafting", "Drafting"), ("review", "Review"), ("approved", "Approved"), ("published", "Published"))
    plan = models.ForeignKey(KnowledgeAgentPlan, on_delete=models.CASCADE, related_name="books")
    domain_ref = models.ForeignKey(KnowledgeDomain, null=True, blank=True, on_delete=models.SET_NULL, related_name="books")
    code = models.SlugField(unique=True)
    title = models.CharField(max_length=400)
    domain = models.CharField(max_length=250)
    objective = models.TextField()
    source_policy = models.TextField(default="منابع معتبر، قابل ردیابی و تفکیک دیدگاه؛ بدون جعل منبع یا ادعای انتشار.")
    status = models.CharField(max_length=20, choices=STATUS, default="planned")
    volume_count = models.PositiveIntegerField(default=1)
    generated_sections = models.PositiveIntegerField(default=0)
    target_sections = models.PositiveIntegerField(default=24)
    content = models.TextField(blank=True)
    outline = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class KnowledgeAgentRun(models.Model):
    STATUS = (("queued", "Queued"), ("running", "Running"), ("completed", "Completed"), ("blocked", "Blocked"), ("failed", "Failed"))
    plan = models.ForeignKey(KnowledgeAgentPlan, on_delete=models.CASCADE, related_name="runs")
    book = models.ForeignKey(KnowledgeBook, on_delete=models.CASCADE, related_name="runs", null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS, default="queued")
    objective = models.TextField()
    output_summary = models.TextField(blank=True)
    approval_required = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
