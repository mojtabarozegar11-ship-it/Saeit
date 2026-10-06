from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models.signals import m2m_changed
from django.utils import timezone
from datetime import timedelta


def factory_grant_expiry_default():
    return timezone.now() + timedelta(days=1)


def factory_approval_expiry_default():
    return timezone.now() + timedelta(days=1)


def factory_evidence_expiry_default():
    return timezone.now() + timedelta(days=90)


def invalidate_factory_research(project_id):
    project = ResearchProject.objects.filter(pk=project_id).select_related("factory_run__product").first()
    if project and project.factory_run_id and project.factory_run.product_id:
        from .factory_governance import invalidate_stale_evidence
        invalidate_stale_evidence(project.factory_run.product)


class T(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class BrandSite(T):
    code = models.SlugField(unique=True)
    name = models.CharField(max_length=120)
    primary_domain = models.CharField(max_length=253, unique=True)
    aliases = models.JSONField(default=list, blank=True)
    default_language = models.CharField(max_length=12, default="en")
    direction = models.CharField(max_length=3, default="ltr")
    theme_key = models.SlugField(default="default")
    seo_title = models.CharField(max_length=200, blank=True)
    seo_description = models.TextField(blank=True)
    active = models.BooleanField(default=True)

    def clean(self):
        self.primary_domain = self.primary_domain.strip().lower().rstrip(".")
        self.aliases = sorted({str(x).strip().lower().rstrip(".") for x in (self.aliases or []) if str(x).strip()})
        if self.direction not in {"ltr", "rtl"}:
            raise ValidationError({"direction": "Direction must be ltr or rtl."})
        if self.primary_domain in self.aliases:
            raise ValidationError({"aliases": "Primary domain must not be repeated as an alias."})

    def __str__(self):
        return self.name


class ResearchProject(T):
    title = models.CharField(max_length=300)
    objective = models.TextField()
    status = models.CharField(max_length=30, default="draft")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="research_projects",
    )
    factory_run = models.OneToOneField("FactoryRun", null=True, blank=True, on_delete=models.PROTECT, related_name="research_project")


class ResearchSource(T):
    project = models.ForeignKey(
        ResearchProject, on_delete=models.CASCADE, related_name="sources"
    )
    title = models.CharField(max_length=500)
    url = models.URLField(blank=True)
    publisher = models.CharField(max_length=300, blank=True)
    content_hash = models.CharField(max_length=128, blank=True)
    retrieved_at = models.DateTimeField(default=timezone.now)
    provenance = models.JSONField(default=dict, blank=True)
    snapshot_hash = models.CharField(max_length=64, blank=True, default="")

    def clean(self):
        if not self.title.strip():
            raise ValidationError({"title": "Source title cannot be empty."})

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        invalidate_factory_research(self.project_id)

    def delete(self, *args, **kwargs):
        project_id = self.project_id
        result = super().delete(*args, **kwargs)
        invalidate_factory_research(project_id)
        return result


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

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        invalidate_factory_research(self.project_id)

    def delete(self, *args, **kwargs):
        project_id = self.project_id
        result = super().delete(*args, **kwargs)
        invalidate_factory_research(project_id)
        return result


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

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        invalidate_factory_research(self.project_id)

    def delete(self, *args, **kwargs):
        project_id = self.project_id
        result = super().delete(*args, **kwargs)
        invalidate_factory_research(project_id)
        return result


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

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        invalidate_factory_research(self.project_id)

    def delete(self, *args, **kwargs):
        project_id = self.project_id
        result = super().delete(*args, **kwargs)
        invalidate_factory_research(project_id)
        return result


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
    # Bridge identifiers make authenticated dispatch safe to retry without
    # creating duplicate work after a caller loses the response.
    bridge_nonce = models.CharField(max_length=128, null=True, blank=True, unique=True)
    bridge_idempotency_key = models.CharField(max_length=128, null=True, blank=True, unique=True)
    bridge_request_digest = models.CharField(max_length=64, blank=True, default="")
    execution_id = models.CharField(max_length=64, blank=True, default="")
    goal = models.TextField(blank=True, default="")
    factory_run = models.ForeignKey("FactoryRun", null=True, blank=True, on_delete=models.PROTECT, related_name="tasks")
    product = models.ForeignKey("Product", null=True, blank=True, on_delete=models.PROTECT, related_name="factory_tasks")
    output_contract = models.JSONField(default=dict)
    prerequisite_snapshot = models.JSONField(default=dict)
    environment = models.CharField(max_length=40, default="development")
    attempt_count = models.PositiveIntegerField(default=0)
    max_attempts = models.PositiveIntegerField(default=3)
    next_retry_at = models.DateTimeField(null=True, blank=True)
    input_data = models.JSONField(default=dict)
    output_data = models.JSONField(default=dict)
    status = models.CharField(max_length=20, default="queued")
    cost = models.DecimalField(max_digits=12, decimal_places=4, default=0)


class ApprovalRequestQuerySet(models.QuerySet):
    def update(self, **kwargs):
        protected_fields = {
            "status", "action_type", "target_type", "target_id",
            "release_manifest_digest", "expires_at", "revoked_at",
        }
        if protected_fields.intersection(kwargs):
            managed_ids = [str(pk) for pk in Product.objects.filter(factory_managed=True).values_list("pk", flat=True)]
            if self.filter(target_type="Product", target_id__in=managed_ids).exists():
                raise ValidationError("Factory activation approvals must pass through the bound owner Approval flow.")
        return super().update(**kwargs)


class FactoryReleaseManifestQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError("Factory release manifests are immutable.")

    def delete(self):
        raise ValidationError("Factory release manifests are immutable.")


class FactoryReleaseGateQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError("Factory release gate state must pass through approve_release().")


class FactoryMarketEligibilityQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError("Market eligibility changes must pass through the audited owner review flow.")


class ApprovalRequest(T):
    objects = models.Manager.from_queryset(ApprovalRequestQuerySet)()
    action_type = models.CharField(max_length=100)
    target_type = models.CharField(max_length=100)
    target_id = models.CharField(max_length=100)
    reason = models.TextField()
    decision_note = models.TextField(blank=True)
    risk = models.CharField(max_length=10, default="high")
    status = models.CharField(max_length=20, default="pending")
    release_manifest_digest = models.CharField(max_length=64, blank=True, default="")
    expires_at = models.DateTimeField(default=factory_approval_expiry_default)
    revoked_at = models.DateTimeField(null=True, blank=True)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="approval_requests",
    )

    @transaction.atomic
    def save(self, *args, **kwargs):
        from .factory_governance import (
            approve_release, bind_release_approval, release_manifest_is_current,
        )
        from .models import FactoryReleaseGate, Product
        product = None
        previous = None
        if self.pk:
            previous = ApprovalRequest.objects.filter(pk=self.pk).first()
            if previous and previous.status == "approved":
                binding = ("action_type", "target_type", "target_id", "release_manifest_digest", "requested_by_id", "expires_at")
                if any(getattr(previous, field) != getattr(self, field) for field in binding):
                    raise ValidationError("An approved release request cannot be rebound or extended.")
                if previous.revoked_at and self.revoked_at != previous.revoked_at:
                    raise ValidationError("A revoked release approval cannot be restored.")
        if self.target_type == "Product" and self.action_type == "activate_product":
            try:
                product = Product.objects.get(pk=self.target_id)
            except Product.DoesNotExist:
                if self.status == "approved":
                    raise ValidationError("Product activation approval target does not exist.")
            if product and product.is_factory_managed and self.status == "pending":
                bind_release_approval(self)
        if self.status == "approved" and self.target_type == "Product":
            if product is None:
                try:
                    product = Product.objects.get(pk=self.target_id)
                except Product.DoesNotExist:
                    raise ValidationError("Product approval target does not exist.")
            if product.is_factory_managed:
                try:
                    gate = FactoryReleaseGate.objects.select_related("run", "artifact", "manifest").get(product=product)
                except FactoryReleaseGate.DoesNotExist as exc:
                    raise ValidationError("Factory Product approval requires its shared Release Gate.") from exc
                revoking_existing_approval = bool(
                    previous and previous.status == "approved"
                    and not previous.revoked_at and self.revoked_at
                )
                if not revoking_existing_approval and (
                    self.action_type != "activate_product"
                    or not self.release_manifest_digest
                    or not self.expires_at
                    or self.expires_at <= timezone.now()
                    or self.revoked_at
                    or not gate.manifest_id
                    or self.release_manifest_digest != gate.manifest.manifest_digest
                    or not release_manifest_is_current(gate.manifest, product, gate.run, gate.artifact)
                ):
                    raise ValidationError("Approval must bind the exact current Factory release manifest and activation action.")
        super().save(*args, **kwargs)
        if self.status == "approved" and not self.revoked_at and product and product.is_factory_managed:
            approve_release(product, self.requested_by, self)


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


class ProductQuerySet(models.QuerySet):
    @transaction.atomic
    def update(self, **kwargs):
        if kwargs.get("factory_managed") is False and any(
            product.is_factory_managed or bool((product.metadata or {}).get("factory_state"))
            for product in self.only("pk", "factory_managed", "metadata")
        ):
            raise ValidationError("Factory-managed identity is permanent.")
        if "metadata" in kwargs and isinstance(kwargs.get("metadata"), dict) and kwargs["metadata"].get("factory_state"):
            raise ValidationError("Factory-managed Products must be established through Product.save().")
        if "metadata" in kwargs and any(
            (product.is_factory_managed or bool((product.metadata or {}).get("factory_state")))
            for product in self.only("metadata")
        ):
            raise ValidationError("Factory Product metadata changes must use save() so dependent evidence is invalidated.")
        activating = kwargs.get("active") is True or (
            "active" in kwargs and not isinstance(kwargs.get("active"), bool)
        )
        if activating:
            from .factory_governance import assert_activation_allowed
            for product in self:
                metadata = kwargs.get("metadata", product.metadata)
                if product.is_factory_managed or bool((metadata or {}).get("factory_state")):
                    product.metadata = metadata
                    assert_activation_allowed(product)
        return super().update(**kwargs)

    @transaction.atomic
    def bulk_update(self, objs, fields, batch_size=None):
        objs = list(objs)
        if "metadata" in fields and any(
            product.is_factory_managed
            or bool((product.metadata or {}).get("factory_state"))
            for product in objs
        ):
            raise ValidationError("Factory Product metadata changes must use save() so dependent evidence is invalidated.")
        if "factory_managed" in fields and any(
            not product.factory_managed and (
                product.is_factory_managed or bool((product.metadata or {}).get("factory_state"))
            ) for product in objs
        ):
            raise ValidationError("Factory-managed identity cannot be removed.")
        if "active" in fields:
            from .factory_governance import assert_activation_allowed
            for product in objs:
                if product.active and product.is_factory_managed:
                    assert_activation_allowed(product)
        return super().bulk_update(objs, fields, batch_size=batch_size)

    def bulk_create(self, objs, **kwargs):
        from .factory_governance import assert_activation_allowed
        for product in objs:
            if isinstance(product.metadata, dict) and product.metadata.get("factory_state"):
                product.factory_managed = True
            if product.active and (product.is_factory_managed or bool((product.metadata or {}).get("factory_state"))):
                assert_activation_allowed(product)
        return super().bulk_create(objs, **kwargs)


class ProductManager(models.Manager.from_queryset(ProductQuerySet)):
    pass


class Product(T):
    objects = ProductManager()
    title = models.CharField(max_length=300)
    product_type = models.CharField(max_length=50)
    price = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    currency = models.CharField(max_length=10, default="IRR")
    active = models.BooleanField(default=False)
    factory_managed = models.BooleanField(default=False, editable=False)
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

    @property
    def is_factory_managed(self):
        if self.factory_managed:
            return True
        if not self.pk:
            return False
        return (
            FactoryRun.objects.filter(product_id=self.pk).exists()
            or FactoryArtifact.objects.filter(product_id=self.pk).exists()
            or FactoryEvidence.objects.filter(product_id=self.pk).exists()
            or FactoryReleaseGate.objects.filter(product_id=self.pk).exists()
        )

    @transaction.atomic
    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")
        factory_managed_before = self.factory_managed
        previous_metadata = None
        if self.pk:
            previous_metadata = Product.objects.filter(pk=self.pk).values_list("metadata", flat=True).first()
        if self.pk:
            old_factory_managed = Product.objects.filter(pk=self.pk).values_list("factory_managed", flat=True).first()
            if old_factory_managed:
                self.factory_managed = True
        if self.is_factory_managed or (isinstance(self.metadata, dict) and self.metadata.get("factory_state")):
            self.factory_managed = True
        if update_fields is not None and factory_managed_before != self.factory_managed:
            kwargs["update_fields"] = set(update_fields) | {"factory_managed"}
        if self.active and self.is_factory_managed:
            from .factory_governance import assert_activation_allowed
            assert_activation_allowed(self)
        super().save(*args, **kwargs)
        if self.pk:
            if isinstance(previous_metadata, dict) and previous_metadata.get("spec") != (self.metadata or {}).get("spec"):
                for run in FactoryRun.objects.filter(product_id=self.pk):
                    run.current_spec_version += 1
                    run.save(update_fields=["current_spec_version", "updated_at"])
            from .factory_governance import invalidate_stale_evidence
            invalidate_stale_evidence(self)


class FactoryRun(T):
    run_id = models.CharField(max_length=64, unique=True)
    product = models.ForeignKey("Product", null=True, blank=True, on_delete=models.PROTECT, related_name="factory_runs")
    goal = models.TextField()
    constraints = models.JSONField(default=list)
    status = models.CharField(max_length=20, default="active")
    environment = models.CharField(max_length=40, default="development")
    current_spec_version = models.PositiveIntegerField(default=1)
    current_artifact_version = models.PositiveIntegerField(default=0)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.product_id:
            Product.objects.filter(pk=self.product_id).update(factory_managed=True)
            from .factory_governance import invalidate_stale_evidence
            invalidate_stale_evidence(self.product)


class FactoryArtifact(T):
    product = models.ForeignKey("Product", on_delete=models.PROTECT, related_name="factory_artifacts")
    run = models.ForeignKey(FactoryRun, on_delete=models.PROTECT, related_name="artifacts")
    created_by_task = models.OneToOneField(AgentTask, on_delete=models.PROTECT, related_name="factory_artifact")
    version = models.PositiveIntegerField()
    reference = models.CharField(max_length=500)
    content_digest = models.CharField(max_length=128, blank=True, default="")
    spec_version = models.PositiveIntegerField()
    class Meta:
        constraints = [models.UniqueConstraint(fields=["product", "version"], name="unique_factory_artifact_version")]

    def save(self, *args, **kwargs):
        if self.pk:
            previous = FactoryArtifact.objects.get(pk=self.pk)
            immutable = ("product_id", "run_id", "created_by_task_id", "version", "reference", "content_digest", "spec_version")
            if any(getattr(previous, field) != getattr(self, field) for field in immutable):
                raise ValidationError("FactoryArtifact versions are immutable.")
        super().save(*args, **kwargs)
        from .factory_governance import invalidate_stale_evidence
        invalidate_stale_evidence(self.product)


class FactoryEvidence(T):
    VALID = "valid"
    STALE = "stale"
    INVALID = "invalid"
    task = models.ForeignKey(AgentTask, on_delete=models.PROTECT, related_name="factory_evidence")
    run = models.ForeignKey(FactoryRun, on_delete=models.PROTECT, related_name="evidence")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="factory_evidence")
    evidence_type = models.CharField(max_length=80)
    prerequisite_digest = models.CharField(max_length=64)
    spec_version = models.PositiveIntegerField(default=1)
    artifact_version = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=12, default=VALID, choices=[(VALID, "Valid"), (STALE, "Stale"), (INVALID, "Invalid")])
    freshness_policy_version = models.CharField(max_length=64, default="factory-evidence-v1")
    valid_until = models.DateTimeField(default=factory_evidence_expiry_default)
    details = models.JSONField(default=dict)
    class Meta:
        constraints = [models.UniqueConstraint(fields=["task", "evidence_type"], name="unique_factory_evidence_per_task")]


class AgentToolGrant(T):
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name="tool_grants")
    capability_code = models.CharField(max_length=100)
    tool_code = models.CharField(max_length=100)
    resource_scope = models.CharField(max_length=200)
    environment = models.CharField(max_length=40)
    active = models.BooleanField(default=True)
    valid_until = models.DateTimeField(default=factory_grant_expiry_default)
    revoked_at = models.DateTimeField(null=True, blank=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=["agent", "capability_code", "tool_code", "resource_scope", "environment"], name="unique_agent_tool_resource_environment_grant")]


class FactoryReleaseGate(T):
    objects = models.Manager.from_queryset(FactoryReleaseGateQuerySet)()
    product = models.OneToOneField(Product, on_delete=models.PROTECT, related_name="factory_release_gate")
    run = models.ForeignKey(FactoryRun, on_delete=models.PROTECT, related_name="release_gates")
    artifact = models.ForeignKey(FactoryArtifact, on_delete=models.PROTECT, related_name="release_gates")
    manifest = models.ForeignKey("FactoryReleaseManifest", null=True, blank=True, on_delete=models.PROTECT, related_name="release_gates")
    status = models.CharField(max_length=24, default="pending_owner_approval")
    approval = models.ForeignKey(ApprovalRequest, null=True, blank=True, on_delete=models.PROTECT, related_name="factory_release_gates")
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="factory_release_approvals")
    approved_at = models.DateTimeField(null=True, blank=True)

    @transaction.atomic
    def save(self, *args, **kwargs):
        if self.status == "approved":
            from .factory_governance import release_manifest_is_current
            approval = ApprovalRequest.objects.select_for_update().filter(pk=self.approval_id).first()
            from django.contrib.auth import get_user_model
            owner = get_user_model().objects.select_for_update().filter(pk=self.approved_by_id).first()
            run = FactoryRun.objects.select_for_update().filter(pk=self.run_id).first()
            artifact = FactoryArtifact.objects.select_for_update().filter(pk=self.artifact_id).first()
            manifest = FactoryReleaseManifest.objects.filter(pk=self.manifest_id).first()
            product = Product.objects.select_for_update().filter(pk=self.product_id).first()
            if not (
                approval and owner and owner.is_superuser and run and artifact and manifest and product
                and self.approved_at and approval.status == "approved" and not approval.revoked_at
                and approval.expires_at and approval.expires_at > timezone.now()
                and approval.action_type == "activate_product" and approval.target_type == "Product"
                and approval.target_id == str(self.product_id)
                and approval.release_manifest_digest == manifest.manifest_digest
                and release_manifest_is_current(manifest, product, run, artifact)
            ):
                raise ValidationError("Only an exact, current owner approval can advance the Factory Release Gate.")
        super().save(*args, **kwargs)


class FactoryReleaseManifest(T):
    objects = models.Manager.from_queryset(FactoryReleaseManifestQuerySet)()
    """Immutable digest binding all release inputs reviewed by the owner."""
    run = models.ForeignKey(FactoryRun, on_delete=models.PROTECT, related_name="release_manifests")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="release_manifests")
    artifact = models.ForeignKey(FactoryArtifact, on_delete=models.PROTECT, related_name="release_manifests")
    spec_version = models.PositiveIntegerField()
    spec_digest = models.CharField(max_length=64)
    artifact_digest = models.CharField(max_length=64)
    locales = models.JSONField(default=list)
    markets = models.JSONField(default=list)
    policy_version = models.CharField(max_length=80)
    evidence_digest = models.CharField(max_length=64)
    eligibility_digest = models.CharField(max_length=64)
    manifest_digest = models.CharField(max_length=64, unique=True)
    snapshot = models.JSONField(default=dict)

    def save(self, *args, **kwargs):
        if self.pk:
            previous = FactoryReleaseManifest.objects.get(pk=self.pk)
            fields = ("run_id", "product_id", "artifact_id", "spec_version", "spec_digest",
                      "artifact_digest", "locales", "markets", "policy_version",
                      "evidence_digest", "eligibility_digest", "manifest_digest", "snapshot")
            if any(getattr(previous, field) != getattr(self, field) for field in fields):
                raise ValidationError("Factory release manifests are immutable.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Factory release manifests are immutable.")

class FactoryMarketEligibility(T):
    objects = models.Manager.from_queryset(FactoryMarketEligibilityQuerySet)()
    """Owner-maintained launch eligibility; Agents can only read this registry."""
    ALLOWED = "allowed"
    PENDING_REVIEW = "pending_review"
    RESTRICTED = "restricted"
    UNSUPPORTED = "unsupported"
    STATUS_CHOICES = [
        (ALLOWED, "Allowed"),
        (PENDING_REVIEW, "Pending Review"),
        (RESTRICTED, "Restricted"),
        (UNSUPPORTED, "Unsupported"),
    ]

    market_code = models.CharField(max_length=16, unique=True)
    eligibility = models.CharField(max_length=20, choices=STATUS_CHOICES)
    evidence_reference = models.URLField(blank=True)
    review_note = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="factory_market_reviews"
    )
    reviewed_at = models.DateTimeField()
    valid_until = models.DateTimeField(null=True, blank=True)

    @transaction.atomic
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        from .factory_governance import invalidate_stale_evidence
        for product in Product.objects.filter(factory_managed=True).iterator():
            markets = (product.metadata or {}).get("market_eligibility") or []
            if any(isinstance(item, dict) and item.get("market_code") == self.market_code for item in markets):
                invalidate_stale_evidence(product)


    class Meta:
        ordering = ["market_code"]

    def clean(self):
        super().clean()
        if self.eligibility == self.ALLOWED:
            errors = {}
            if not self.evidence_reference:
                errors["evidence_reference"] = "Allowed markets require a reviewable evidence reference."
            if not str(self.review_note or "").strip():
                errors["review_note"] = "Allowed markets require a documented review note."
            if not self.valid_until:
                errors["valid_until"] = "Allowed market reviews must expire and be renewed."
            elif self.reviewed_at and self.valid_until <= self.reviewed_at:
                errors["valid_until"] = "Review expiry must be later than the review time."
            if errors:
                raise ValidationError(errors)
        if self.reviewed_by_id and not self.reviewed_by.is_superuser:
            raise ValidationError({"reviewed_by": "Only the owner account may approve market eligibility."})

    def __str__(self):
        return f"{self.market_code}: {self.eligibility}"


def _invalidate_finding_evidence(sender, instance, action, **kwargs):
    if action in {"post_add", "post_remove", "post_clear"}:
        invalidate_factory_research(instance.project_id)


m2m_changed.connect(
    _invalidate_finding_evidence,
    sender=Finding.evidence.through,
    dispatch_uid="core.factory_finding_evidence_lineage",
)


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
