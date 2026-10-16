from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class T(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class ResearchProject(T):
    title = models.CharField(max_length=300)
    objective = models.TextField()
    status = models.CharField(max_length=30, default="draft")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="research_projects",
    )


class ResearchSource(T):
    project = models.ForeignKey(
        ResearchProject, on_delete=models.CASCADE, related_name="sources"
    )
    title = models.CharField(max_length=500)
    url = models.URLField(blank=True)
    publisher = models.CharField(max_length=300, blank=True)
    content_hash = models.CharField(max_length=128, blank=True)

    def clean(self):
        if not self.title.strip():
            raise ValidationError({"title": "Source title cannot be empty."})


class Evidence(T):
    project = models.ForeignKey(
        ResearchProject, on_delete=models.CASCADE, related_name="evidence"
    )
    source = models.ForeignKey(
        ResearchSource, on_delete=models.CASCADE, related_name="evidence"
    )
    passage = models.TextField()
    confidence = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )

    def clean(self):
        if self.source_id and self.project_id:
            source_project_id = (
                ResearchSource.objects.filter(pk=self.source_id)
                .values_list("project_id", flat=True)
                .first()
            )
            if source_project_id is not None and source_project_id != self.project_id:
                raise ValidationError(
                    {"source": "Evidence source must belong to the same research project."}
                )
        if self.confidence is not None and not (0 <= self.confidence <= 1):
            raise ValidationError({"confidence": "Confidence must be between 0 and 1."})


class Finding(T):
    project = models.ForeignKey(
        ResearchProject, on_delete=models.CASCADE, related_name="findings"
    )
    title = models.CharField(max_length=300)
    statement = models.TextField()
    confidence = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    limitation = models.TextField(blank=True)
    evidence = models.ManyToManyField(Evidence, blank=True, related_name="findings")

    def clean(self):
        if self.confidence is not None and not (0 <= self.confidence <= 1):
            raise ValidationError({"confidence": "Confidence must be between 0 and 1."})


class Report(T):
    project = models.ForeignKey(
        ResearchProject, on_delete=models.CASCADE, related_name="reports"
    )
    title = models.CharField(max_length=300)
    version = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=30, default="draft")
    content = models.JSONField(default=dict)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["project", "version"], name="unique_report_version_per_project"
            )
        ]


class Agent(T):
    code = models.SlugField(unique=True)
    name = models.CharField(max_length=200)
    mission = models.TextField()
    risk_level = models.CharField(max_length=10, default="low")
    active = models.BooleanField(default=False)


class AgentCapability(T):
    code = models.SlugField(unique=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    risk_level = models.CharField(max_length=10, default="low")
    active = models.BooleanField(default=True)
    agents = models.ManyToManyField(Agent, blank=True, related_name="capabilities")


class AgentTask(T):
    agent = models.ForeignKey(Agent, on_delete=models.PROTECT, related_name="tasks")
    project = models.ForeignKey(
        ResearchProject,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="agent_tasks",
    )
    action_type = models.CharField(max_length=100, default="")
    capability_code = models.CharField(max_length=100, default="")
    risk_snapshot = models.CharField(max_length=10, default="low")
    execution_id = models.CharField(max_length=64, blank=True, default="")
    attempt_count = models.PositiveIntegerField(default=0)
    max_attempts = models.PositiveIntegerField(default=3)
    input_data = models.JSONField(default=dict)
    output_data = models.JSONField(default=dict)
    status = models.CharField(max_length=20, default="queued")
    cost = models.DecimalField(max_digits=12, decimal_places=4, default=0)


class ApprovalRequest(T):
    action_type = models.CharField(max_length=100)
    target_type = models.CharField(max_length=100)
    target_id = models.CharField(max_length=100)
    reason = models.TextField()
    decision_note = models.TextField(blank=True)
    risk = models.CharField(max_length=10, default="high")
    status = models.CharField(max_length=20, default="pending")
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="approval_requests",
    )


class ApprovalGrant(T):
    """Short-lived, scoped, one-time execution grant derived from an approved request."""
    approval = models.ForeignKey(
        ApprovalRequest, on_delete=models.CASCADE, related_name="grants"
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="approval_grants"
    )
    scope = models.JSONField(default=dict)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["approval", "expires_at"]),
            models.Index(fields=["actor", "expires_at"]),
        ]

class AuditLog(T):
    actor_type = models.CharField(max_length=30)
    actor_id = models.CharField(max_length=100, blank=True)
    action = models.CharField(max_length=200)
    target_type = models.CharField(max_length=100, blank=True)
    target_id = models.CharField(max_length=100, blank=True)
    before_state = models.JSONField(default=dict)
    after_state = models.JSONField(default=dict)
    trace_id = models.CharField(max_length=100, db_index=True)


class KnowledgeArticle(T):
    source_report = models.ForeignKey(
        "Report", on_delete=models.PROTECT, null=True, blank=True, related_name="knowledge_articles"
    )
    title = models.CharField(max_length=300)
    slug = models.SlugField(unique=True)
    content = models.TextField()
    version = models.PositiveIntegerField(default=1)
    published = models.BooleanField(default=False)


class Product(T):
    title = models.CharField(max_length=300)
    product_type = models.CharField(max_length=50)
    price = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    currency = models.CharField(max_length=10, default="IRR")
    active = models.BooleanField(default=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="products",
        null=True,
        blank=True,
    )
    knowledge_article = models.ForeignKey(
        "KnowledgeArticle",
        on_delete=models.PROTECT,
        related_name="products",
        null=True,
        blank=True,
    )
    metadata = models.JSONField(default=dict)


class Order(T):
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="orders"
    )
    status = models.CharField(max_length=30, default="pending")
    total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    currency = models.CharField(max_length=10, default="IRR")


class OrderItem(T):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="order_items")
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=10)

    @property
    def line_total(self):
        return self.unit_price * self.quantity


class PaymentIntent(T):
    order = models.OneToOneField(Order, on_delete=models.PROTECT, related_name="payment_intent")
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=10)
    idempotency_key = models.CharField(max_length=128, unique=True)
    status = models.CharField(max_length=30, default="awaiting_approval")
    provider = models.CharField(max_length=50, default="not_configured")
    provider_reference = models.CharField(max_length=200, blank=True, default="")


class LedgerEntry(T):
    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name="ledger_entries")
    payment_intent = models.ForeignKey(
        PaymentIntent, on_delete=models.PROTECT, related_name="ledger_entries",
        null=True, blank=True
    )
    entry_type = models.CharField(max_length=30)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=10)
    reference = models.CharField(max_length=200, unique=True)
    metadata = models.JSONField(default=dict)


class PaymentWebhookEvent(T):
    provider = models.CharField(max_length=50)
    event_id = models.CharField(max_length=200)
    event_type = models.CharField(max_length=50)
    payment_intent = models.ForeignKey(
        PaymentIntent, on_delete=models.PROTECT,
        related_name="webhook_events", null=True, blank=True
    )
    payload_hash = models.CharField(max_length=128)
    status = models.CharField(max_length=30, default="received")
    processed_at = models.DateTimeField(null=True, blank=True)
    error = models.TextField(blank=True, default="")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "event_id"],
                name="unique_payment_webhook_event",
            )
        ]


class ChatSession(T):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="master_agent_chat_sessions",
    )
    title = models.CharField(max_length=300, blank=True)
    status = models.CharField(max_length=20, default="active")


class ChatMessage(T):
    session = models.ForeignKey(
        ChatSession, on_delete=models.CASCADE, related_name="messages"
    )
    role = models.CharField(max_length=20)
    content = models.TextField()
    metadata = models.JSONField(default=dict)

from .newsletter_models import NewsletterAgentLink, NewsletterPublication, NewsletterSchedule, NewsletterSource, NewsletterStory

from .blog_models import BlogDistributionPlan, BlogPage, BlogPublication, BlogTranslation, ExternalBlogTarget

from .company_content_models import CompanyContentLink, CompanyGalleryMedia

from .company_inquiry_models import CompanyInquiry


# Company Activity Intelligence Agent models are kept in a focused module.
from .company_activity_models import CompanyActivityAgentPlan, CompanyActivityReport
from .economic_trade_models import TradeMailbox, TradeEmailOutbox, TradeEmailAudit


class EducationTrack(T):
    key = models.SlugField(max_length=80, unique=True)
    title = models.CharField(max_length=200)
    meta = models.CharField(max_length=200, blank=True)
    description = models.TextField()
    level = models.CharField(max_length=80, blank=True)
    active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    class Meta:
        ordering = ["sort_order", "id"]

class EducationCourse(T):
    track = models.ForeignKey(EducationTrack, on_delete=models.CASCADE, related_name="courses")
    title = models.CharField(max_length=300)
    slug = models.SlugField(max_length=180, unique=True)
    summary = models.TextField()
    syllabus = models.JSONField(default=list)
    prerequisites = models.TextField(blank=True)
    outcome = models.TextField(blank=True)
    price = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    currency = models.CharField(max_length=10, default="IRR")
    is_free = models.BooleanField(default=False)
    active = models.BooleanField(default=False)
    approved = models.BooleanField(default=False)
    version = models.PositiveIntegerField(default=1)
    product = models.OneToOneField("Product", on_delete=models.PROTECT, null=True, blank=True, related_name="education_course")
    quality_status = models.CharField(max_length=20, default="draft", choices=[
        ("draft", "Draft"), ("review", "Review"), ("approved", "Approved"),
        ("published", "Published"), ("archived", "Archived"),
    ])
    quality_note = models.TextField(blank=True)
    quality_checked_at = models.DateTimeField(null=True, blank=True)
    class Meta:
        ordering = ["track__sort_order", "id"]

class EducationResource(T):
    course = models.ForeignKey(EducationCourse, on_delete=models.CASCADE, related_name="resources", null=True, blank=True)
    kind = models.CharField(max_length=40)
    title = models.CharField(max_length=300)
    content = models.TextField(blank=True)
    file_url = models.URLField(blank=True)
    is_free = models.BooleanField(default=False)
    active = models.BooleanField(default=False)
    approved = models.BooleanField(default=False)
    sort_order = models.PositiveIntegerField(default=0)
    class Meta:
        ordering = ["sort_order", "id"]

class EducationLesson(T):
    course = models.ForeignKey(EducationCourse, on_delete=models.CASCADE, related_name="lessons")
    title = models.CharField(max_length=300)
    summary = models.TextField(blank=True)
    lesson_type = models.CharField(max_length=40, default="lesson")
    duration_minutes = models.PositiveIntegerField(default=0)
    content = models.TextField(blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    is_free_preview = models.BooleanField(default=False)
    active = models.BooleanField(default=False)
    class Meta:
        ordering = ["sort_order", "id"]


class EducationPresentation(T):
    course = models.ForeignKey(EducationCourse, on_delete=models.CASCADE, related_name="presentations")
    title = models.CharField(max_length=300)
    audience = models.CharField(max_length=40, default="teacher", choices=[
        ("teacher", "Teacher"), ("professor", "Professor"), ("coach", "Coach"),
    ])
    description = models.TextField(blank=True)
    slide_count = models.PositiveIntegerField(default=0)
    file_url = models.URLField(blank=True)
    source_file = models.CharField(max_length=500, blank=True)
    presenter_notes = models.TextField(blank=True)
    lesson_plan = models.JSONField(default=list)
    classroom_activities = models.JSONField(default=list)
    assessment_notes = models.TextField(blank=True)
    version = models.PositiveIntegerField(default=1)
    is_free = models.BooleanField(default=False)
    active = models.BooleanField(default=False)
    approved = models.BooleanField(default=False)
    quality_status = models.CharField(max_length=20, default="draft", choices=[
        ("draft", "Draft"), ("review", "Review"), ("approved", "Approved"),
        ("published", "Published"), ("archived", "Archived"),
    ])
    class Meta:
        ordering = ["course__id", "id"]


class EducationEnrollment(T):
    course = models.ForeignKey(EducationCourse, on_delete=models.CASCADE, related_name="enrollments")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="education_enrollments")
    status = models.CharField(max_length=20, default="active", choices=[
        ("active", "Active"), ("completed", "Completed"), ("cancelled", "Cancelled"),
    ])
    source = models.CharField(max_length=30, default="direct")
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["course", "user"], name="unique_education_enrollment")]
        indexes = [models.Index(fields=["user", "status"])]


class EducationProgress(T):
    enrollment = models.ForeignKey(EducationEnrollment, on_delete=models.CASCADE, related_name="progress")
    lesson = models.ForeignKey(EducationLesson, on_delete=models.CASCADE, related_name="progress")
    completed = models.BooleanField(default=False)
    progress_percent = models.PositiveSmallIntegerField(default=0)
    last_position = models.PositiveIntegerField(default=0)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["enrollment", "lesson"], name="unique_education_progress")]
        indexes = [models.Index(fields=["enrollment", "completed"])]


class EducationBookmark(T):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="education_bookmarks")
    lesson = models.ForeignKey(EducationLesson, on_delete=models.CASCADE, related_name="bookmarks")
    note = models.TextField(blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "lesson"], name="unique_education_bookmark")]


class EducationAssessment(T):
    course = models.ForeignKey(EducationCourse, on_delete=models.CASCADE, related_name="assessments")
    title = models.CharField(max_length=300)
    description = models.TextField(blank=True)
    passing_score = models.PositiveSmallIntegerField(default=70)
    active = models.BooleanField(default=False)
    approved = models.BooleanField(default=False)


class EducationQuestion(T):
    assessment = models.ForeignKey(EducationAssessment, on_delete=models.CASCADE, related_name="questions")
    prompt = models.TextField()
    choices = models.JSONField(default=list)
    correct_index = models.PositiveIntegerField(default=0)
    explanation = models.TextField(blank=True)
    sort_order = models.PositiveIntegerField(default=0)


class EducationAttempt(T):
    assessment = models.ForeignKey(EducationAssessment, on_delete=models.CASCADE, related_name="attempts")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="education_attempts")
    answers = models.JSONField(default=dict)
    score = models.PositiveSmallIntegerField(default=0)
    passed = models.BooleanField(default=False)
    submitted_at = models.DateTimeField(auto_now_add=True)


class EducationCertificate(T):
    enrollment = models.OneToOneField(EducationEnrollment, on_delete=models.CASCADE, related_name="certificate")
    code = models.CharField(max_length=40, unique=True)
    title = models.CharField(max_length=300)
    verification_note = models.TextField(blank=True)
    issued_at = models.DateTimeField(auto_now_add=True)
