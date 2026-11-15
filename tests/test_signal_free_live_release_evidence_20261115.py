"""Static and live-read-only contract checks for Moj Prop educational acquisition.

Never sends mail, POSTs customer data, initiates TRON or deploys to host.
"""
import hashlib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "templates/moj-prop-v4"
LIVE_PROBE = ROOT / ".github/workflows/mojprop-public-readonly-24h-evidence-20261115.yml"
RELEASE = ROOT / ".github/workflows/mojprop-backend-controlled-release-20261115.yml"
STATIC_RELEASE = ROOT / ".github/workflows/mojplaywin-moj-prop-deploy.yml"


class SignalFreeLiveReleaseEvidenceTests(unittest.TestCase):
    def test_exact_historical_approved_live_page_versions_are_distinct(self):
        plain = (SOURCE / "baselines/signals-index-before-free.html").read_bytes()
        public_free = (SOURCE / "baselines/signals-index-after-free-preview.html").read_bytes()
        current = (SOURCE / "signals/index.html").read_bytes()
        self.assertEqual(len({hashlib.sha256(value).hexdigest()
                              for value in (plain, public_free, current)}), 3)
        self.assertNotIn(b'id="free-preview"', plain)
        self.assertIn(b'id="free-preview"', public_free)
        self.assertNotIn(b'id="free-education-membership"', public_free)
        self.assertIn(b'id="free-education-membership"', current)
        self.assertIn(b'/moj-signal-free-subscribe/', current)

    def test_static_installer_exact_baseline_or_refuse_unknown_content(self):
        text = (ROOT / "scripts/update_mojplaywin_moj_prop_catalog.py").read_text("utf-8")
        self.assertIn("BASELINE_SIGNAL_FREE_PREVIEW", text)
        self.assertIn("before not in (after, old_signal, free_preview_signal)", text)
        self.assertIn("refusing replacement", text)
        self.assertIn("def verified_manifest(", text)
        self.assertIn("Backup checksum mismatch", text)

    def test_live_probe_checks_new_root_api_without_posting_or_credentials(self):
        text = LIVE_PROBE.read_text("utf-8")
        self.assertIn("https://mojplaywin.com/moj-signal-free-subscribe/", text)
        self.assertIn("https://mojplaywin.com/moj-prop/signals/", text)
        self.assertIn("https://mojplaywin.com/saman/market-signals/", text)
        self.assertIn("https://mojplaywin.com/ar/saman/market-signals/", text)
        self.assertIn("PUBLIC_SIGNAL_FREE_API_CONTRACT=", text)
        self.assertIn("PUBLIC_SIGNAL_FREE_EMAIL_FLAG=", text)
        self.assertIn("PUBLIC_SIGNAL_OPTIN_FORM=", text)
        self.assertIn("PUBLIC_SIGNAL_DESK_EXACT_RELEASE=", text)
        self.assertIn("PUBLIC_SIGNAL_DESK_SAFE_UPGRADE=", text)
        self.assertIn("PUBLIC_SIGNAL_LIVE_DOCUMENT_KIND=", text)
        self.assertIn("PUBLIC_SIGNAL_LIVE_CONTENT_REVIEW_REQUIRED=true", text)
        self.assertIn("PUBLIC_SIGNAL_LIVE_SHA256_PREFIX=", text)
        self.assertNotIn("print(raw)", text)
        self.assertNotIn("print(parsed.title)", text)
        self.assertIn('persist-credentials: false', text)
        self.assertIn('live == source.read_bytes()', text)
        self.assertIn("PUBLIC_MOJPLAYWIN_HOST_ROUTE_GATE=", text)
        self.assertIn("PUBLIC_SIGNAL_FREE_CONFIRMED_MEMBER_COUNT=not_checked", text)
        self.assertIn("PUBLIC_SIGNAL_PAID_PAYMENT_DELIVERY=not_checked", text)
        self.assertIn("GET routes only", text)
        self.assertNotIn("curl -X POST", text)
        self.assertNotIn("send_mail(", text)
        self.assertNotIn("secrets.", text)
        self.assertNotIn("Authorization: Bearer", text)

    def test_live_probe_parses_contract_without_printing_csrf(self):
        text = LIVE_PROBE.read_text("utf-8")
        for marker in ("mojtaba.bot.ai", "free-historical-research-updates",
                       'type(data.get("csrf_token")) is str',
                       'type(data.get("enabled")) is bool'):
            self.assertIn(marker, text)
        self.assertNotIn('print(data["csrf_token"])', text)
        self.assertNotIn('print(data["email"])', text)

    def test_source_merged_does_not_activate_free_email_subscription(self):
        text = (ROOT / "config/settings.py").read_text("utf-8")
        self.assertIn(
            'MOJTABA_SIGNAL_FREE_SIGNUP_ENABLED = env.bool("MOJTABA_SIGNAL_FREE_SIGNUP_ENABLED", default=False)',
            text,
        )
        views = (ROOT / "core/signal_free_views.py").read_text("utf-8")
        self.assertIn('if not _smtp_ready():', views)
        self.assertIn('subscriber.status = "pending"', views)
        self.assertIn('max_age=_CONFIRM_TTL', views)

    def test_all_host_release_write_jobs_stay_manual_only(self):
        backend = RELEASE.read_text("utf-8")
        static = STATIC_RELEASE.read_text("utf-8")
        self.assertIn("github.event_name == 'workflow_dispatch'", backend)
        self.assertIn("MOJPROP_BACKUP_RESTORE_VERIFIED", backend)
        self.assertIn("MOJPROP_ROLLBACK_VERIFIED", backend)
        self.assertIn("MOJPROP_TENANT_ISOLATION_VERIFIED", backend)
        self.assertIn("inputs.owner_approved_static_release == true", static)
        self.assertIn("MOJ_PROP_LIVE_STATIC_COMPATIBILITY=CHECKED_READ_ONLY", backend)
        self.assertIn("MOJ_PROP_LIVE_STATIC_COMPATIBILITY=CHECKED_READ_ONLY", static)
        self.assertLess(
            backend.index("- name: Fail closed on unknown live Signal Desk BEFORE any writes"),
            backend.index("- name: Deploy Moj Prop intake backend with backup and migration"),
        )
        self.assertLess(
            static.index("- name: Fail closed on unknown live Signal Desk BEFORE any writes"),
            static.index("- name: Update only /moj-prop/ commercial catalog"),
        )
        self.assertIn("SIGNAL_FREE_PUBLIC_PAGE=PASS", backend)
        self.assertIn("MOJTABA_FREE_SIGNUP_API_PREFLIGHT=PASS", static)
        self.assertNotIn("moj_signal_free_stats --apply", backend)


if __name__ == "__main__":
    unittest.main()
