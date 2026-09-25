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
