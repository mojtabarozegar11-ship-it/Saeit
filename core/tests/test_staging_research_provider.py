import pytest
from django.test import override_settings

from core.factory_agent_runtime import FactoryAgentBlocked
from core.self_hosted_research_provider import SelfHostedStagingResearchProvider


@override_settings(SAEIT_ENV="staging")
def test_self_hosted_provider_is_explicitly_real_and_keyless():
    provider = SelfHostedStagingResearchProvider()
    assert provider.real_research is True
    assert provider.provider_name == "self-hosted-staging"
    assert provider.search_endpoint.startswith("https://search.brave.com/")


@override_settings(SAEIT_ENV="production")
def test_self_hosted_provider_fails_closed_outside_staging():
    with pytest.raises(FactoryAgentBlocked, match="SAEIT_ENV=staging"):
        SelfHostedStagingResearchProvider()


def test_search_link_extraction_excludes_search_engine_links():
    body = '<a href="/url?q=https%3A%2F%2Fexample.com%2Freport&x=1">x</a>' \
           '<a href="https://www.google.com/preferences">g</a>'
    assert SelfHostedStagingResearchProvider._search_links(body) == ["https://example.com/report"]


def test_html_extraction_normalizes_whitespace():
    text = '<style>hidden</style><p>Useful   evidence</p>'
    assert SelfHostedStagingResearchProvider._text_snapshot(text, 'text/html') == 'Useful evidence'


@override_settings(SAEIT_ENV='staging')
def test_search_retries_next_query_after_network_failure(monkeypatch):
    provider = SelfHostedStagingResearchProvider()
    seen = []

    def fake_get(url, **kwargs):
        seen.append(url)
        if len(seen) == 1:
            raise RuntimeError('network timeout')
        if len(seen) == 2:
            return url, 'text/html', '<a href="https://public.example/report">report</a>'
        return url, 'text/plain', 'Independent research evidence'

    monkeypatch.setattr(provider, '_get', fake_get)
    records = provider.search(
        goal='test', constraints=[], plan={'queries': ['first', 'second']},
        task=None, authorization=None, authorization_check=lambda *args: True,
        timeout_seconds=10, max_results=1, max_snapshot_bytes=10000,
        max_redirects=0, safe_url_policy=lambda url: url.startswith('https://'),
    )
    assert len(records) == 1
    assert len(seen) == 3
    assert records[0]['snapshot'] == 'Independent research evidence'
