"""Opt-in audience only for historical educational research by mojtaba.bot.ai.

A request or purchased report never implicitly creates this membership.
Marketing mail needs explicit verified consent; no trading or paid entitlement.
"""
from django.db import models


class MojSignalFreeSubscription(models.Model):
    STATUS = (
        ("pending", "Pending independent email confirmation"),
        ("confirmed", "Confirmed free educational updates"),
        ("unsubscribed", "Unsubscribed / suppression retained"),
    )
    email = models.EmailField(max_length=254, unique=True)
    status = models.CharField(max_length=14, choices=STATUS, default="pending")
    nonce = models.CharField(max_length=48)
    consent_at = models.DateTimeField()
    consent_version = models.CharField(max_length=24, default="edu-free-v1")
    confirmation_sent_at = models.DateTimeField(null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    unsubscribed_at = models.DateTimeField(null=True, blank=True)
    source = models.CharField(max_length=32, default="signal-desk")
    ip_hash = models.CharField(max_length=64, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=("status", "created_at"), name="mojsigfree_status_idx"),
            models.Index(fields=("ip_hash", "confirmation_sent_at"), name="mojsigfree_ip_sent_idx"),
        ]
        verbose_name = "Mojtaba.bot.ai free educational subscriber"
        verbose_name_plural = "Mojtaba.bot.ai free educational subscribers"

    def __str__(self):
        # Do not expose personal email addresses in generic logs.
        return f"signal-free:{self.pk or 'unsaved'}:{self.status}"
