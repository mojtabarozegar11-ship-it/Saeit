"""C90: keep the free-signal source contract deployable and fail-closed.

The live 404 observed in the read-only probe was a deployment gap, not
permission to enable email. This test prevents future source drift between
the URL route, backend contract, public form and controlled release bundle.
"""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class SignalFreeSourceLiveContractTests(unittest.TestCase):
    def setUp(self):
        self.urls = (ROOT / "config/urls.py").read_text(encoding="utf-8")
        self.views = (ROOT / "core/signal_free_views.py").read_text(encoding="utf-8")
        self.model = (ROOT / "core/signal_free_models.py").read_text(encoding="utf-8")
        self.page = (
            ROOT / "templates/moj-prop-v4/signals/index.html"
        ).read_text(encoding="utf-8")
        self.release = (
            ROOT
            / ".github/workflows/mojprop-backend-controlled-release-20261115.yml"
        ).read_text(encoding="utf-8")

    def test_all_three_public_routes_are_registered(self):
        for route in (
            'path("moj-signal-free-subscribe/"',
            'path("moj-signal-free-confirm/',
            'path("moj-signal-free-unsubscribe/',
        ):
            self.assertIn(route, self.urls)

    def test_get_contract_is_readiness_only_and_identifies_one_bot(self):
        self.assertIn("def signal_free_subscribe(request):", self.views)
        self.assertIn('"agent": "mojtaba.bot.ai"', self.views)
        self.assertIn('"enabled": _smtp_ready()', self.views)
        self.assertIn('"paid_entitlement": False', self.views)
        self.assertIn("csrf_token", self.views)
        self.assertIn("POST requests a verification email only", self.views)

    def test_email_is_fail_closed_until_explicit_smtp_switch(self):
        self.assertIn("MOJTABA_SIGNAL_FREE_SIGNUP_ENABLED", self.views)
        self.assertIn("Verified free email registration is not currently available.", self.views)
        self.assertIn("No registration was confirmed.", self.views)
        self.assertIn("No marketing will be sent until you explicitly confirm.", self.views)

    def test_public_page_is_educational_and_wires_the_same_endpoint(self):
        self.assertIn('id="free-education-membership"', self.page)
        self.assertIn('id="signal-free-signup"', self.page)
        self.assertIn("const url='/moj-signal-free-subscribe/';", self.page)
        self.assertIn("not a live signal", self.page)
        self.assertIn("a paid service", self.page)
        self.assertIn("r.status!==202", self.page)

    def test_controlled_release_contains_route_backend_migration_and_smoke_gate(self):
        for item in (
            "config/urls.py",
            "core/signal_free_models.py",
            "core/signal_free_views.py",
            "core/migrations/0046_signal_free_subscription.py",
            "SIGNAL_FREE_OPTIN_BACKEND_GET=PASS",
            "https://mojplaywin.com/moj-signal-free-subscribe/",
            "Roll back Moj Prop backend on failed install or failed smoke",
        ):
            self.assertIn(item, self.release)

    def test_subscriber_model_retains_suppression_state(self):
        self.assertIn('("confirmed", "Confirmed free educational updates")', self.model)
        self.assertIn('("unsubscribed", "Unsubscribed / suppression retained")', self.model)
        self.assertIn("consent_version", self.model)
        self.assertIn("ip_hash", self.model)


if __name__ == "__main__":
    unittest.main()
