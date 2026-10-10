"""Stage-4 provider boundary security tests, independent of external connectivity."""
from django.test import SimpleTestCase, override_settings

from core.factory_agent_runtime import (
    FactoryAgentBlocked,
    _safe_research_url,
    configured_research_provider,
)


class Stage4ProviderBoundaryTests(SimpleTestCase):
    def test_rejects_internal_and_metadata_endpoints(self):
        for url in (
            "http://127.0.0.1/",
            "http://169.254.169.254/latest/meta-data/",
            "http://10.0.0.1/",
            "http://192.168.1.1/",
            "http://localhost/",
            "https://metadata.google.internal/",
            "file:///etc/passwd",
            "https://user:pass@example.com/",
            "https://example.com:8443/",
        ):
            with self.subTest(url=url):
                self.assertFalse(_safe_research_url(url))

    def test_rejects_fixture_source_in_real_research(self):
        self.assertFalse(_safe_research_url("fixture://fake-source"))
        self.assertTrue(_safe_research_url("fixture://fake-source", allow_fixture=True))

    def test_accepts_public_https_url_at_policy_boundary(self):
        self.assertTrue(_safe_research_url("https://example.org/research"))
        self.assertTrue(_safe_research_url("https://example.org:443/research"))

    @override_settings(FACTORY_RESEARCH_PROVIDER="")
    def test_missing_real_provider_fails_closed(self):
        with self.assertRaisesRegex(FactoryAgentBlocked, "PROVIDER_UNAVAILABLE"):
            configured_research_provider()

    @override_settings(FACTORY_RESEARCH_PROVIDER="core.factory_agent_runtime.FixtureResearchProvider")
    def test_fixture_cannot_be_configured_as_real_provider(self):
        with self.assertRaisesRegex(FactoryAgentBlocked, "not approved for real evidence"):
            configured_research_provider()
