import pytest
from django.test import override_settings

from core.factory_agent_runtime import FactoryAgentBlocked
from core.self_hosted_research_provider import SelfHostedStagingResearchProvider


@override_settings(SAEIT_ENV="staging")
def test_self_hosted_provider_is_explicitly_real_and_keyless():
    provider = SelfHostedStagingResearchProvider()
    assert provider.real_research is True
    assert provider.provider_name == "self-hosted-staging"
    assert provider.search_endpoint.startswith("https://")


@override_settings(SAEIT_ENV="production")
def test_self_hosted_provider_fails_closed_outside_staging():
    with pytest.raises(FactoryAgentBlocked, match="SAEIT_ENV=staging"):
        SelfHostedStagingResearchProvider()


def test_search_link_extraction_excludes_search_engine_links():
    body = '<a href="/url?q=https%3A%2F%2Fexample.com%2Freport&x=1">x</a>' \
           '<a href="https://www.google.com/preferences">g</a>'
    assert SelfHostedStagingResearchProvider._search_links(body) == ["https://example.com/report"]
