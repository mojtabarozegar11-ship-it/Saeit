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
