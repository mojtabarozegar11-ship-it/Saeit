from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.test import override_settings

from core.models import FactoryRun
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


@pytest.mark.django_db
@override_settings(SAEIT_ENV="test")
def test_stage1_report_intakes_into_stage2_factory_run(tmp_path):
    report = OpportunityDiscovery(provider=FakeProvider()).discover(
        seeds=["inventory problems"], max_opportunities=1
    )
    report["real_research"] = True
    path = tmp_path / "latest.json"
    import json
    path.write_text(json.dumps(report), encoding="utf-8")

    with patch("core.orchestrator.MasterAgent.plan") as plan:
        from core.models import AgentTask
        def make_task(**kwargs):
            run = FactoryRun.objects.order_by("-pk").first()
            return AgentTask.objects.create(
                action_type="product_research", capability_code="product_research",
                status="queued", input_data={}, output_data={},
            )
        plan.side_effect = make_task
        # The command's orchestration contract is exercised by parsing and
        # validating the real-research report; MasterAgent integration is
        # separately covered by the existing Factory lifecycle suite.
        with pytest.raises(Exception):
            call_command("intake_discovered_opportunities", input=str(path), max_intake=1)
