"""Security admission tests; fetch-time DNS pinning is a separate required gate."""
import pytest
from core.factory_research_v2 import acceptable_discovery_url


@pytest.mark.parametrize("url", [
    "https://example.org/article",
    "https://www.example.com:443/a?q=1",
])
def test_public_discovery_candidate(url):
    assert acceptable_discovery_url(url)


@pytest.mark.parametrize("url", [
    "http://example.org/", "https://localhost/", "https://a.local/",
    "https://metadata.internal/", "https://127.0.0.1/",
    "https://169.254.169.254/latest/meta-data/",
    "https://[::1]/", "https://user:pass@example.org/",
    "https://example.org:8443/", "https://example.org/#fragment",
    "https://example.org/ bad", "https://example.org/\nheader",
    "https://example.org:bad/", "https://example.org.",
    "https://example.org" + "x" * 1801,
    "", None,
])
def test_unsafe_discovery_candidate_rejected(url):
    assert not acceptable_discovery_url(url)
