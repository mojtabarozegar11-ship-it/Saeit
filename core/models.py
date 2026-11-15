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


class CommerceFunnelEvent(T):
    EVENT_CHOICES = (
        ("view_store", "Store view"),
        ("view_item", "Product view"),
        ("begin_checkout", "Checkout opened"),
        ("invoice_created", "Invoice created"),
        ("payment_confirmed", "Payment confirmed"),
        ("delivery_success", "Delivery succeeded"),
        ("delivery_failure", "Delivery failed"),
    )
    event_name = models.CharField(max_length=32, choices=EVENT_CHOICES)
    source = models.CharField(max_length=40, blank=True, default="")
    medium = models.CharField(max_length=40, blank=True, default="")
    campaign = models.CharField(max_length=80, blank=True, default="")
    product = models.ForeignKey(
        "Product",
        on_delete=models.PROTECT,
        related_name="funnel_events",
        null=True,
        blank=True,
    )

    class Meta:
        indexes = [
            models.Index(fields=["event_name", "created_at"]),
            models.Index(fields=["product", "event_name", "created_at"]),
        ]


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


class MojPropRequest(T):
    """Public Moj Prop request intake; no payment or automated advice is created."""
    ROUTE_CHOICES = (
        ("blueprint", "Prop-program design"),
        ("signals", "Educational signals and market brief"),
        ("brief", "Private market brief"),
        ("audit", "mojtaba.bot.ai commercial-gate audit"),
        ("digital", "Digital product purchase inquiry"),
    )
    HORIZON_CHOICES = (
        ("urgent", "Today / urgent"),
        ("week", "This week"),
        ("month", "This month"),
        ("review", "Initial review only"),
    )
    STATUS_CHOICES = (
        ("new", "New"),
        ("reviewing", "Reviewing"),
        ("offer_sent", "Written offer sent"),
        ("approved", "Approved"),
        ("delivered", "Delivered"),
        ("closed", "Closed"),
        ("spam", "Spam / rejected"),
    )
    request_id = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=200)
    email = models.EmailField()
    route = models.CharField(max_length=30, choices=ROUTE_CHOICES)
    horizon = models.CharField(max_length=20, choices=HORIZON_CHOICES)
    notes = models.TextField()
    # Product inquiry is a lead only, never a paid order.
    product_id = models.PositiveBigIntegerField(null=True, blank=True)
    consent = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="new")
    source = models.CharField(max_length=80, default="moj-prop")
    ip_hash = models.CharField(max_length=64, blank=True, default="")
    user_agent = models.CharField(max_length=300, blank=True, default="")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    internal_note = models.TextField(blank=True, default="")

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=("status", "created_at"), name="mojprop_status_created_idx"),
            models.Index(fields=("email", "created_at"), name="mojprop_email_created_idx"),
            models.Index(fields=("ip_hash", "created_at"), name="mojprop_ip_created_idx"),
        ]

class MojPropOffer(T):
    """A priced manual-service proposal, never a paid order or delivered signal.

    This record cannot charge a buyer, send an email or mark an order paid.
    Buyers receive a quote only through an explicitly authorised channel.
    """
    STATUS_CHOICES = (
        ("draft", "Draft - not issued"),
        ("approved", "Reviewed for manual issuance"),
        ("issued", "Manually issued - delivery not promised"),
        ("accepted", "Acceptance recorded - not paid"),
        ("cancelled", "Cancelled"),
        ("expired", "Expired"),
    )
    CURRENCIES = (("USD", "US dollar"), ("IRR", "Iranian rial"))
    lead = models.ForeignKey(
        MojPropRequest, on_delete=models.PROTECT, related_name="commercial_offers"
    )
    version = models.PositiveSmallIntegerField(default=1)
    title = models.CharField(max_length=180)
    scope = models.TextField()
    exclusions = models.TextField(
        default="No live funded account, live trading, guaranteed returns or subscriptions."
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, choices=CURRENCIES, default="USD")
    delivery_days = models.PositiveSmallIntegerField(default=7)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="draft")
    expires_at = models.DateTimeField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    issued_at = models.DateTimeField(null=True, blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    acceptance_reference = models.CharField(max_length=180, blank=True, default="")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="mojprop_offers", null=True, blank=True,
    )
    internal_note = models.TextField(blank=True, default="")

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("lead", "version"), name="mojprop_one_offer_per_version"
            ),
            models.CheckConstraint(
                condition=models.Q(version__gte=1) & models.Q(version__lte=999),
                name="mojprop_valid_offer_version",
            ),
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="mojprop_offer_positive_amount",
            ),
            models.CheckConstraint(
                condition=models.Q(delivery_days__gte=1) & models.Q(delivery_days__lte=90),
                name="mojprop_offer_delivery_days_range",
            ),
        ]

    def clean(self):
        from decimal import Decimal, InvalidOperation
        from django.utils import timezone
        super().clean()
        errors = {}
        if not self.title or not self.title.strip():
            errors["title"] = "A concrete deliverable title is required."
        if not self.scope or len(self.scope.strip()) < 50:
            errors["scope"] = "Specify at least 50 characters of real scope."
        try:
            value = self.amount
            if (type(value) is not Decimal or not value.is_finite()
                    or value <= 0 or value != value.quantize(Decimal("0.01"))):
                errors["amount"] = "A finite, positive, two-decimal quote is required."
        except (InvalidOperation, TypeError, ValueError):
            errors["amount"] = "Invalid quote."
        if (type(self.delivery_days) is not int
                or not 1 <= self.delivery_days <= 90):
            errors["delivery_days"] = "Delivery must be between 1 and 90 days."
        if type(self.version) is not int or not 1 <= self.version <= 999:
            errors["version"] = "Proposal version must be 1-999."
        if self.lead_id and self.lead.route not in ("blueprint", "signals", "brief", "audit", "digital"):
            errors["lead"] = "Unsupported commercial request."
        if self.pk:
            prior = type(self).objects.filter(pk=self.pk).first()
            if prior:
                # An issued/accepted/terminal quote is an immutable commercial
                # snapshot. Price negotiation must create a higher version.
                if prior.status in ("issued", "accepted", "cancelled", "expired"):
                    protected = ("lead_id", "version", "title", "scope",
                                 "exclusions", "amount", "currency",
                                 "delivery_days", "issued_at", "reviewed_at", "expires_at")
                    if any(getattr(prior, field) != getattr(self, field) for field in protected):
                        errors["status"] = "Frozen quote terms cannot be rewritten; issue a new version."
                transitions = {
                    "draft": ("draft", "approved", "cancelled"),
                    "approved": ("approved", "draft", "issued", "cancelled"),
                    "issued": ("issued", "accepted", "cancelled", "expired"),
                    "accepted": ("accepted", "cancelled"),
                    "cancelled": ("cancelled",),
                    "expired": ("expired",),
                }
                if self.status not in transitions.get(prior.status, ()):
                    errors["status"] = "Quote status transition is not permitted."

        if self.status in ("approved", "issued", "accepted") and self.reviewed_at is None:
            errors["reviewed_at"] = "A manual review timestamp is required."
        if self.status in ("issued", "accepted"):
            if self.issued_at is None:
                errors["issued_at"] = "Only manually issued written offers can be tracked."
            if self.expires_at is None:
                errors["expires_at"] = "A written offer must have an expiry date."
        now = timezone.now()
        if self.reviewed_at and self.reviewed_at > now:
            errors["reviewed_at"] = "Manual review cannot be recorded in the future."
        if self.issued_at and self.issued_at > now:
            errors["issued_at"] = "A written quote cannot be marked issued in the future."
        if self.issued_at and self.reviewed_at and self.issued_at < self.reviewed_at:
            errors["issued_at"] = "Issuance cannot precede manual review."
        if self.status in ("draft", "approved") and self.issued_at is not None:
            errors["issued_at"] = "An unissued proposal must not carry issuance evidence."
        has_acceptance_reference = (
            isinstance(self.acceptance_reference, str)
            and bool(self.acceptance_reference.strip())
        )
        if self.status in ("draft", "approved", "issued") and (
            self.accepted_at is not None or has_acceptance_reference
        ):
            errors["accepted_at"] = "Unaccepted offers must not include acceptance evidence."
        if self.issued_at and self.expires_at and self.expires_at <= self.issued_at:
            errors["expires_at"] = "Expiry must follow issuance."
        if self.status == "issued" and self.expires_at and self.expires_at <= now:
            errors["expires_at"] = "Do not issue an already-expired commercial proposal."
        if self.status == "accepted":
            if not self.accepted_at or not has_acceptance_reference:
                errors["acceptance_reference"] = "Record verifiable customer acceptance before calling a quote accepted."
            if (self.accepted_at and self.issued_at and self.accepted_at < self.issued_at):
                errors["accepted_at"] = "Customer cannot accept before a quote was issued."
            if (self.accepted_at and self.expires_at and self.accepted_at > self.expires_at):
                errors["accepted_at"] = "An expired proposal cannot be accepted."
        if self.accepted_at and self.accepted_at > timezone.now():
            errors["accepted_at"] = "Customer acceptance cannot be in the future."
        if errors:
            raise ValidationError(errors)

    @property
    def manual_quote_text(self):
        """Copyable draft text; intentionally not an invoice or a payment request."""
        return (
            f"MOJ PROP / mojtaba.bot.ai - MANUAL PROPOSAL (NOT A PAYMENT INVOICE)\n"
            f"Reference: {self.lead.request_id} / version {self.version}\n"
            f"Service: {self.get_lead_route_display()}\n"
            f"Catalog product ID: {self.lead.product_id or 'n/a'}\n"
            f"Deliverable: {self.title}\n"
            f"Scope: {self.scope}\n"
            f"Exclusions: {self.exclusions}\n"
            f"Quoted amount: {self.amount} {self.currency}\n"
            f"Target delivery: {self.delivery_days} day(s) after a separate agreement.\n"
            f"Proposal status: {self.status}; expires: {self.expires_at.isoformat() if self.expires_at else 'not issued'}\n"
            "No payment has been collected; a lawful payment route and written agreement are required."
        )

    def get_lead_route_display(self):
        return dict(MojPropRequest.ROUTE_CHOICES).get(self.lead.route, "Unknown")


class MojPropDeliveryEvidence(T):
    """Auditable handoff of one accepted proposal's private deliverable.

    No message is sent here, no download is exposed, and a written reference
    alone is never treated as proof of a blockchain/card payment.
    """
    STATUS_CHOICES = (
        ("prepared", "Artifact prepared privately"),
        ("sent", "External handoff recorded"),
        ("acknowledged", "Customer acknowledgement recorded"),
    )
    offer = models.OneToOneField(
        MojPropOffer, on_delete=models.PROTECT, related_name="delivery_evidence"
    )
    artifact_sha256 = models.CharField(max_length=64)
    artifact_name = models.CharField(max_length=180)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="prepared")
    # An actual legal clearance/credit term must be recorded before dispatch;
    # this field does not assert a payment or an amount was received.
    clearance_reference = models.CharField(max_length=180, blank=True, default="")
    handoff_reference = models.CharField(max_length=180, blank=True, default="")
    handed_off_at = models.DateTimeField(null=True, blank=True)
    acknowledgment_reference = models.CharField(max_length=180, blank=True, default="")
    acknowledged_at = models.DateTimeField(null=True, blank=True)

    def clean(self):
        import re
        from django.utils import timezone
        super().clean()
        errors = {}
        if (type(self.artifact_sha256) is not str or re.fullmatch(
                r"[0-9a-f]{64}", self.artifact_sha256) is None
                or self.artifact_sha256 == "0" * 64):
            errors["artifact_sha256"] = "A real private deliverable SHA256 is required."
        if not self.artifact_name or not self.artifact_name.strip():
            errors["artifact_name"] = "Name the prepared deliverable."
        if self.offer_id and self.offer.status != "accepted":
            errors["offer"] = "Deliverables require an accepted written offer."
        if self.status in ("sent", "acknowledged"):
            if (not self.clearance_reference.strip()
                    or not self.handoff_reference.strip()
                    or self.handed_off_at is None):
                errors["handoff_reference"] = "Handoff requires a clearance, timestamp and delivery reference."
        if self.status == "acknowledged":
            if not self.acknowledgment_reference.strip() or self.acknowledged_at is None:
                errors["acknowledgment_reference"] = "The customer acknowledgment must be independently recorded."
        elif self.acknowledged_at or self.acknowledgment_reference.strip():
            errors["acknowledgment_reference"] = "Unacknowledged deliveries cannot carry buyer acknowledgment."
        if self.handed_off_at and self.handed_off_at > timezone.now():
            errors["handed_off_at"] = "Cannot dispatch a deliverable in the future."
        if self.acknowledged_at and (self.acknowledged_at > timezone.now()
                                    or (self.handed_off_at and
                                        self.acknowledged_at < self.handed_off_at)):
            errors["acknowledged_at"] = "Acknowledgment must follow handoff."
        if self.pk:
            previous = type(self).objects.filter(pk=self.pk).first()
            if previous:
                allowed = {
                    "prepared": ("prepared", "sent"),
                    "sent": ("sent", "acknowledged"),
                    "acknowledged": ("acknowledged",),
                }
                if self.status not in allowed.get(previous.status, ()):
                    errors["status"] = "Delivery lifecycle cannot be reversed."
                if previous.status in ("sent", "acknowledged"):
                    protected = ("offer_id", "artifact_sha256", "artifact_name",
                                 "clearance_reference", "handoff_reference",
                                 "handed_off_at")
                    if any(getattr(self, field) != getattr(previous, field)
                           for field in protected):
                        errors["status"] = "Dispatched deliverable evidence is immutable."
        if errors:
            raise ValidationError(errors)
