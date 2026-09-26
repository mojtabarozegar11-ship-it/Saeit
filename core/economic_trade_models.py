from django.db import models


class TradeMailbox(models.Model):
    code = models.SlugField(unique=True)
    display_name = models.CharField(max_length=200)
    email_address = models.EmailField(blank=True)
    active = models.BooleanField(default=False)
    allow_outbound = models.BooleanField(default=False)
    require_policy_gate = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Trade Mailbox"
        verbose_name_plural = "Trade Mailboxes"


class TradeEmailOutbox(models.Model):
    mailbox = models.ForeignKey(TradeMailbox, on_delete=models.PROTECT, related_name="outbox")
    idempotency_key = models.CharField(max_length=128, unique=True)
    recipient = models.EmailField()
    subject = models.CharField(max_length=300)
    body = models.TextField()
    trade_context = models.JSONField(default=dict)
    status = models.CharField(max_length=30, default="draft")
    provider_reference = models.CharField(max_length=200, blank=True, default="")
    error = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["mailbox", "status"]), models.Index(fields=["created_at"])]


class TradeEmailAudit(models.Model):
    outbox = models.ForeignKey(TradeEmailOutbox, on_delete=models.PROTECT, related_name="audits")
    action = models.CharField(max_length=50)
    actor_type = models.CharField(max_length=30, default="economic-agent")
    trace_id = models.CharField(max_length=100, db_index=True)
    metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
