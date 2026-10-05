import hashlib
import json
from unittest.mock import MagicMock, patch
from django.test import SimpleTestCase, override_settings
from core.staging_provider import TavilyStagingProvider
from core.factory_agent_runtime import FactoryAgentBlocked
from core.staging_readiness import validate_acceptance_report


@override_settings(SAEIT_ENV="staging", STAGING_RESEARCH_API_KEY="test-only")
class StagingProviderTests(SimpleTestCase):
    def invoke(self, payload, **overrides):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps(payload).encode()
        opener = MagicMock()
        opener.open.return_value = response
        args = dict(goal="goal", constraints=[], plan={"queries": ["goal"]}, task=None,
                    authorization=None, authorization_check=lambda *a: True, timeout_seconds=10,
                    max_results=6, max_snapshot_bytes=10000, max_redirects=0,
                    safe_url_policy=lambda url: url.startswith("https://public.example/"))
        args.update(overrides)
        with patch("core.staging_provider.build_opener", return_value=opener):
            result = TavilyStagingProvider().search(**args)
        return result, opener

    def test_raw_snapshot_is_preserved_and_search_rank_is_not_commercial_evidence(self):
        text = "Demand and pricing observation, without a commercial rating."
        rows, opener = self.invoke({"request_id": "real-response-shape", "results": [
            {"url": "https://public.example/report", "raw_content": text, "score": 0.99}]})
        self.assertEqual(rows[0]["snapshot_sha256"], hashlib.sha256(text.encode()).hexdigest())
        self.assertEqual(rows[0]["economic_factors"], {})
        self.assertEqual(opener.open.call_args.args[0].full_url, "https://api.tavily.com/search")

    def test_generated_answer_without_raw_content_cannot_be_evidence(self):
        with self.assertRaises(FactoryAgentBlocked):
            self.invoke({"answer": "invented", "results": [{"url": "https://public.example/a", "content": "snippet"}]})

    def test_unsafe_sources_and_revoked_authorization_rejected(self):
        with self.assertRaises(FactoryAgentBlocked):
            self.invoke({"results": [{"url": "http://127.0.0.1/", "raw_content": "private"}]})
        with self.assertRaises(FactoryAgentBlocked):
            self.invoke({"results": []}, authorization_check=lambda *a: False)

    @override_settings(STAGING_RESEARCH_API_KEY="")
    def test_missing_credential_fails_closed(self):
        with self.assertRaises(FactoryAgentBlocked):
            TavilyStagingProvider()

    def test_minimal_old_report_no_longer_passes(self):
        self.assertFalse(validate_acceptance_report({"environment": "staging", "stages_completed": ["product_launch_candidate"]}))
