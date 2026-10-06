import json
from types import SimpleNamespace
from unittest.mock import patch

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


@override_settings(SAEIT_ENV="test")
def test_stage1_report_intakes_into_stage2_factory_run(tmp_path, capsys):
    report = OpportunityDiscovery(provider=FakeProvider()).discover(
        seeds=["inventory problems"], max_opportunities=1
    )
    report["real_research"] = True
    path = tmp_path / "latest.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    fake_task = SimpleNamespace(pk=71, factory_run=SimpleNamespace(run_id="run-stage2-1"))

    with patch(
        "core.management.commands.intake_discovered_opportunities.AutonomousBrain.plan_product_factory_step",
        return_value=fake_task,
    ) as planner:
        call_command("intake_discovered_opportunities", input=str(path), max_intake=1)

    assert planner.call_count == 1
    payload = planner.call_args.kwargs["payload"]
    assert payload["constraints"]["source_stage"] == "opportunity_discovery"
    assert payload["constraints"]["discovery_opportunity_id"].startswith("opp-")
    output = capsys.readouterr().out
    assert '"status": "PASS"' in output
    assert '"task_id": 71' in output


@override_settings(SAEIT_ENV="test")
def test_stage2_intake_rejects_non_real_discovery(tmp_path):
    path = tmp_path / "latest.json"
    path.write_text(json.dumps({
        "status": "PASS", "real_research": False,
        "opportunities": [{"opportunity_id": "opp-x", "problem": "x", "evidence_urls": ["https://example.com"]}],
    }), encoding="utf-8")
    with pytest.raises(Exception, match="not real-research PASS evidence"):
        call_command("intake_discovered_opportunities", input=str(path))
