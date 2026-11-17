"""Protect the free audience distinction, privacy and SMTP prerequisite."""
from datetime import timedelta
from io import StringIO
from pathlib import Path
from django.conf import settings
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone
from core.signal_free_views import _smtp_ready
from core.signal_free_models import MojSignalFreeSubscription


class SignalFreeSMTPGateTests(SimpleTestCase):
    @override_settings(
        MOJTABA_SIGNAL_FREE_SIGNUP_ENABLED=False,
        EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
        EMAIL_HOST="mail.example.org", EMAIL_HOST_USER="operator",
        EMAIL_HOST_PASSWORD="fake-test-only", DEFAULT_FROM_EMAIL="research@example.org",
        EMAIL_USE_TLS=True, EMAIL_USE_SSL=False, EMAIL_PORT=587,
    )
    def test_separate_owner_flag_is_required(self):
        self.assertFalse(_smtp_ready())

    @override_settings(
        MOJTABA_SIGNAL_FREE_SIGNUP_ENABLED=True,
        EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend",
        EMAIL_HOST="mail.example.org", EMAIL_HOST_USER="operator",
        EMAIL_HOST_PASSWORD="fake-test-only", DEFAULT_FROM_EMAIL="research@example.org",
        EMAIL_USE_TLS=True, EMAIL_USE_SSL=False, EMAIL_PORT=587,
    )
    def test_console_email_backend_is_forbidden_in_production(self):
        self.assertFalse(_smtp_ready())

    @override_settings(
        MOJTABA_SIGNAL_FREE_SIGNUP_ENABLED=True,
        EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
        EMAIL_HOST="mail.example.org", EMAIL_HOST_USER="operator",
        EMAIL_HOST_PASSWORD="", DEFAULT_FROM_EMAIL="research@example.org",
        EMAIL_USE_TLS=True, EMAIL_USE_SSL=False, EMAIL_PORT=587,
    )
    def test_missing_smtp_password_fails_closed(self):
        self.assertFalse(_smtp_ready())

    @override_settings(
        MOJTABA_SIGNAL_FREE_SIGNUP_ENABLED=True,
        EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
        EMAIL_HOST="mail.example.org", EMAIL_HOST_USER="operator",
        EMAIL_HOST_PASSWORD="fake-test-only", DEFAULT_FROM_EMAIL="research@example.org",
        EMAIL_USE_TLS=True, EMAIL_USE_SSL=True, EMAIL_PORT=587,
    )
    def test_ambiguous_both_ssl_and_tls_fails_closed(self):
        self.assertFalse(_smtp_ready())

    @override_settings(
        MOJTABA_SIGNAL_FREE_SIGNUP_ENABLED=True,
        EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
        EMAIL_HOST="mail.example.org", EMAIL_HOST_USER="operator",
        EMAIL_HOST_PASSWORD="fake-test-only", DEFAULT_FROM_EMAIL="research@example.org",
        EMAIL_USE_TLS=True, EMAIL_USE_SSL=False, EMAIL_PORT=587,
    )
    def test_valid_configuration_shape_only_does_not_assert_verified_smtp(self):
        self.assertTrue(_smtp_ready())

    def test_public_free_form_has_separate_explicit_opt_in_and_no_auto_payment(self):
        html = (Path(settings.BASE_DIR) / "templates/moj-prop-v4/signals/index.html").read_text("utf-8")
        self.assertIn('id="free-education-membership"', html)
        self.assertIn('id="signal-free-consent"', html)
        self.assertIn('id="signal-free-email"', html)
        self.assertIn('id="signal-free-submit"', html)
        self.assertIn("button id=\"signal-free-submit\" type=\"submit\" disabled", html)
        self.assertIn("No marketing membership is created by the ordinary Moj Prop request form", html)
        self.assertIn("status!=='verification_if_eligible'", html)


class SignalFreeOperationsTests(TestCase):
    def create_member(self, email, status, when):
        return MojSignalFreeSubscription.objects.create(
            email=email, status=status, nonce="no-network-local-test-nonce",
            consent_at=when, confirmation_sent_at=when, source="signal-desk",
            confirmed_at=when if status == "confirmed" else None,
            unsubscribed_at=when if status == "unsubscribed" else None,
            ip_hash="0" * 64,
        )

    def test_stats_never_count_pending_as_active_or_claim_money(self):
        now = timezone.now()
        self.create_member("p@example.org", "pending", now)
        self.create_member("a@example.org", "confirmed", now)
        self.create_member("u@example.org", "unsubscribed", now)
        out = StringIO()
        call_command("moj_signal_free_stats", stdout=out)
        import json
        snapshot=json.loads(out.getvalue())
        self.assertEqual(snapshot["pending_email_confirmation"], 1)
        self.assertEqual(snapshot["confirmed_free_members"], 1)
        self.assertEqual(snapshot["unsubscribed_suppressed"], 1)
        self.assertIsNone(snapshot["paid_customers_verified"])
        self.assertIsNone(snapshot["settled_revenue_usd"])
        self.assertNotIn("@example.org", out.getvalue())

    def test_purge_requires_apply_and_preserves_confirmed_suppression(self):
        old = timezone.now() - timedelta(days=45)
        pending = self.create_member("old@example.org", "pending", old)
        active = self.create_member("active@example.org", "confirmed", old)
        suppressed = self.create_member("suppressed@example.org", "unsubscribed", old)
        MojSignalFreeSubscription.objects.filter(pk__in=[pending.pk, active.pk, suppressed.pk]).update(created_at=old)
        out = StringIO()
        call_command("moj_signal_free_purge", stdout=out)
        self.assertIn("removed=0", out.getvalue())
        self.assertEqual(MojSignalFreeSubscription.objects.count(), 3)
        out = StringIO()
        call_command("moj_signal_free_purge", apply=True, stdout=out)
        self.assertIn("removed=1", out.getvalue())
        self.assertFalse(MojSignalFreeSubscription.objects.filter(pk=pending.pk).exists())
        self.assertTrue(MojSignalFreeSubscription.objects.filter(pk=active.pk).exists())
        self.assertTrue(MojSignalFreeSubscription.objects.filter(pk=suppressed.pk).exists())
