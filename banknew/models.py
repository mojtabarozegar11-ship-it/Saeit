"""Django-only persistence; not installed or routed in the shared application."""
from django.conf import settings
from django.db import models


class GoogleAccountLink(models.Model):
    google_subject = models.CharField(max_length=255, unique=True)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                related_name="mojpay_google_identity")
    verified_email = models.EmailField(max_length=320)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "mojpay_google_account_links"


class LoginChallenge(models.Model):
    nonce_digest = models.CharField(max_length=64, primary_key=True)
    session_digest = models.CharField(max_length=64, db_index=True)
    issued_at = models.DateTimeField(db_index=True)
    consumed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "mojpay_google_login_challenges"
