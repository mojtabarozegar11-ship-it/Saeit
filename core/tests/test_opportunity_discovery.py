import json

import pytest
from django.core.management import call_command
from django.test import override_settings

from core.opportunity_discovery import OpportunityDiscovery


class FakeProvider:
    provider_name = "fake-real"
    real_research = True

    def search(self, **kwargs):
        seed = kwargs["goal"]
        return [{
            "passage": ("Small businesses repeatedly report manual spreadsheet work, "
                        "inventory errors, pricing uncertainty, and time-consuming reconciliation. " + seed),
            "final_url": "https://example.com/report",
        }]


@override_settings(SAEIT_ENV="test")
def test_discovery_returns_bounded_deduplicated_pool():
    report = OpportunityDiscovery(provider=FakeProvider()).discover(
        seeds=["inventory problems", "inventory problems"], max_opportunities=10
    )
    assert report["status"] == "PASS"
    assert report["opportunity_count"] == 1
    assert report["opportunities"][0]["opportunity_id"].startswith("opp-")
    assert report["next_stage"] == "market_research"


@override_settings(SAEIT_ENV="production")
def test_discovery_fails_closed_in_production():
    with pytest.raises(Exception, match="disabled in production"):
        OpportunityDiscovery(provider=FakeProvider()).discover(seeds=["x"])
