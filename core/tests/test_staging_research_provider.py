import pytest

from core.factory_agent_runtime import FactoryAgentBlocked
from core.staging_research_provider import TavilyStagingResearchProvider


def test_staging_provider_is_explicitly_real_and_named():
    provider = TavilyStagingResearchProvider()
    assert provider.real_research is True
    assert provider.provider_name == "tavily-staging"
    assert provider.endpoint == "https://api.tavily.com/search"


def test_staging_provider_fails_closed_without_local_secret(monkeypatch):
    monkeypatch.delenv("STAGING_RESEARCH_API_KEY", raising=False)
    with pytest.raises(FactoryAgentBlocked, match="STAGING_RESEARCH_API_KEY"):
        TavilyStagingResearchProvider()._request("test", timeout_seconds=1, max_results=2)
