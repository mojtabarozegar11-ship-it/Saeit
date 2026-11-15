"""Six actual offline commercial service artifacts through ONE economic master worker.

All fixtures are synthetic. No live site, email, payment, CRM buyer record,
provider, broker, external network or production directory is contacted.
"""
from io import StringIO
from pathlib import Path
from unittest.mock import patch
import hashlib
import os

import pytest
from django.core.management import call_command

from core.economic_tool_pack import build_economic_gateway, service_package
from core.mojtaba_commercial_services import InvalidService, generate
from core.models import Agent, AgentTask


EXAMPLES = {
    "AGR-01": {
        "units_sold": "2400", "unit_price_toman": "120000",
        "unit_variable_cost_toman": "75000", "fixed_cost_toman": "48000000",
        "price_change_pct": "10", "yield_change_pct": "15",
    },
    "RS-01": {"claims": [
        {"claim_id": "C-01", "source_id": "DATA-2026-A",
         "unit": "kg_per_ha", "reproducible": True},
        {"claim_id": "C-02", "source_id": "", "unit": "percent",
         "reproducible": False},
    ]},
    "RS-02": {"area_m2": "10000", "scenarios": [
        {"name": "baseline", "flow_m3_per_hour": "15", "hours": "8"},
        {"name": "alternative", "flow_m3_per_hour": "12", "hours": "8"},
    ]},
    "RS-03": {"treatments": ["control", "treatment_A", "treatment_B"],
              "replicates": 4, "seed": 1405},
    "WEB-01": {"visitors": 1000, "inquiries": 65, "qualified": 27,
               "paid_orders": 8, "delivered": 6},
    "SEO-01": {"checks": [
        {"id": "IDX-01", "category": "indexing", "state": "unknown",
         "priority": "high", "evidence_ref": ""},
        {"id": "MOB-01", "category": "mobile", "state": "fail",
         "priority": "high", "evidence_ref": "MOBILE-AUDIT-1"},
    ]},
}


@pytest.mark.parametrize("code", sorted(EXAMPLES))
def test_each_real_service_engine_produces_distinct_calculated_output(code):
    doc = generate({"service_code": code, "data": EXAMPLES[code]},
                   "0" * 64)
    assert code in doc
    assert "Mojtaba.bot.ai" in doc
    assert "پرداخت" in doc
    assert len(doc) > 250
    assert doc != generate({"service_code": "AGR-01", "data": EXAMPLES["AGR-01"]},
                           "0" * 64) if code != "AGR-01" else True


@pytest.mark.django_db
@pytest.mark.parametrize("code", sorted(EXAMPLES))
def test_all_six_services_are_executed_through_single_existing_worker(
        tmp_path, code):
    with patch("core.mojtaba_commercial_services.Path.home",
               return_value=tmp_path):
        call_command("seed_online_income_agents", verbosity=0)
        master = Agent.objects.get(code="economic-master-agent", active=True)
        task = AgentTask.objects.create(
            agent=master, action_type="income_service_package",
            capability_code="income_service_package",
            risk_snapshot="medium",
            input_data={"service_code": code, "data": EXAMPLES[code]},
            status="queued",
        )
        output = StringIO()
        call_command("run_economic_worker", task_id=task.pk, stdout=output)
        task.refresh_from_db()
        assert task.status == "completed"
        assert task.output_data["verified_effect"] is True
        assert task.output_data["customer_delivered"] is False
        assert task.output_data["revenue_not_assessed"] is True
        assert "revenue_not_assessed=true" in output.getvalue()
        private = tmp_path / "factory-runtime/private/mojtaba-bot-ai/service-deliverables"
        result = list(private.glob("*.md"))
        assert len(result) == 1
        assert code in result[0].name
        assert os.stat(result[0]).st_mode & 0o777 == 0o600
        assert result[0].stat().st_size > 300
        assert task.output_data["evidence"]["kind"] == "private_service_package"


def test_gateway_registers_only_a_private_internal_service_tool():
    spec = build_economic_gateway().describe()["income_service_package"]
    assert spec["enabled"] is True
    assert spec["risk"] == "medium"


def test_rejects_unscoped_client_data_and_html_before_any_write(tmp_path):
    with patch("core.mojtaba_commercial_services.Path.home",
               return_value=tmp_path):
        invalid = {"service_code": "SEO-01", "data": {"checks": [
            {"id": "customer@example.com", "category": "indexing",
             "state": "pass", "priority": "high", "evidence_ref": "secret"}
        ]}}
        with pytest.raises(ValueError, match="SERVICE_PACKAGE_VALIDATION_FAILED"):
            service_package(invalid)
    assert not list(tmp_path.rglob("*.md"))


def test_duplicate_same_input_not_claimed_as_another_product(tmp_path):
    payload = {"service_code": "AGR-01", "data": EXAMPLES["AGR-01"]}
    with patch("core.mojtaba_commercial_services.Path.home",
               return_value=tmp_path):
        first = service_package(payload)
        second = service_package(payload)
    assert first["verified_effect"] is True
    assert second["verified_effect"] is False
    assert first["evidence"]["kind"] == "private_service_package"
    assert second["evidence"]["kind"] == "existing_service_package"
    assert len(list(tmp_path.rglob("*.md"))) == 1


def test_original_input_is_rejected_if_customer_contact_fields_are_injected():
    data = dict(EXAMPLES["WEB-01"])
    data["customer_email"] = "private@example.com"
    with pytest.raises(InvalidService):
        generate({"service_code": "WEB-01", "data": data}, "0" * 64)


@pytest.mark.parametrize("bad", [
    {"service_code": "AGR-01", "data": {"units_sold": -1}},
    {"service_code": "WEB-01", "data": {**EXAMPLES["WEB-01"], "delivered": 100}},
    {"service_code": "RS-03", "data": {**EXAMPLES["RS-03"], "treatments": ["x", "x"]}},
    {"service_code": "SEO-01", "data": {"checks": [
        {"id": "IDX-01", "category": "indexing", "state": "pass",
         "priority": "high", "evidence_ref": ""}
    ]}},
])
def test_invalid_result_cannot_be_counted_as_deliverable(bad):
    with pytest.raises(InvalidService):
        generate(bad, "0" * 64)


def test_concurrent_identical_artifact_is_counted_only_once(tmp_path):
    """A second worker loses the atomic link race without a fake new effect."""
    payload = {"service_code": "AGR-01", "data": EXAMPLES["AGR-01"]}
    real_link = os.link

    def first_writer_wins(src, dest, **kwargs):
        real_link(src, dest, **kwargs)
        raise FileExistsError("concurrent writer already committed the same file")

    with patch("core.mojtaba_commercial_services.Path.home",
               return_value=tmp_path), patch(
        "core.economic_tool_pack.os.link", side_effect=first_writer_wins
    ):
        result = service_package(payload)
    assert result["verified_effect"] is False
    assert result["revenue_not_assessed"] is True
    assert len(list(tmp_path.rglob("*.md"))) == 1


def test_concurrent_different_bytes_never_clobber_prior_private_work(tmp_path):
    payload = {"service_code": "AGR-01", "data": EXAMPLES["AGR-01"]}

    def competing_writer(src, dest, **kwargs):
        Path(dest).write_text("other trusted content", encoding="utf-8")
        raise FileExistsError("another writer")

    with patch("core.mojtaba_commercial_services.Path.home",
               return_value=tmp_path), patch(
        "core.economic_tool_pack.os.link", side_effect=competing_writer
    ):
        with pytest.raises(ValueError, match="CONCURRENT_OUTPUT_COLLISION"):
            service_package(payload)
    files = list(tmp_path.rglob("*.md"))
    assert len(files) == 1
    assert files[0].read_text(encoding="utf-8") == "other trusted content"


@pytest.mark.parametrize("code,data", [
    ("AGR-01", {**EXAMPLES["AGR-01"], "unit_price_toman": 0.1}),
    ("RS-02", {**EXAMPLES["RS-02"], "area_m2": 0.1}),
])
def test_monetary_and_irrigation_calculations_reject_binary_floats(code, data):
    with pytest.raises(InvalidService, match="exact numeric"):
        generate({"service_code": code, "data": data}, "0" * 64)


def test_cli_atomic_promotion_is_private_and_idempotent(tmp_path, monkeypatch):
    import json
    import sys
    from core import mojtaba_commercial_services as engine
    source = tmp_path / "input.json"
    source.write_text(json.dumps({"service_code": "AGR-01", "data": EXAMPLES["AGR-01"]}), encoding="utf-8")
    monkeypatch.setattr(engine.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(sys, "argv", ["mojtaba-service", str(source)])
    assert engine.main() == 0
    artifacts = list(tmp_path.rglob("*.md"))
    assert len(artifacts) == 1
    assert artifacts[0].stat().st_mode & 0o077 == 0
    assert engine.main() == 0
    assert len(list(tmp_path.rglob("*.md"))) == 1


def test_cli_concurrent_write_cannot_overwrite_existing_artifact(tmp_path, monkeypatch):
    import json
    import sys
    from core import mojtaba_commercial_services as engine
    source = tmp_path / "input.json"
    source.write_text(json.dumps({"service_code": "AGR-01", "data": EXAMPLES["AGR-01"]}), encoding="utf-8")
    monkeypatch.setattr(engine.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(sys, "argv", ["mojtaba-service", str(source)])

    def competing_writer(src, dest):
        Path(dest).write_text("previous private deliverable", encoding="utf-8")
        raise FileExistsError("another worker won")
    monkeypatch.setattr(engine.os, "link", competing_writer)
    assert engine.main() == 2
    files = list(tmp_path.rglob("*.md"))
    assert len(files) == 1
    assert files[0].read_text(encoding="utf-8") == "previous private deliverable"


def test_cli_refuses_symlink_input_without_creating_artifact(tmp_path, monkeypatch):
    import json
    import sys
    from core import mojtaba_commercial_services as engine
    actual = tmp_path / "actual.json"
    actual.write_text(json.dumps({"service_code": "AGR-01", "data": EXAMPLES["AGR-01"]}), encoding="utf-8")
    alias = tmp_path / "alias.json"
    alias.symlink_to(actual)
    monkeypatch.setattr(engine.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(sys, "argv", ["mojtaba-service", str(alias)])
    assert engine.main() == 2
    assert not list(tmp_path.rglob("*.md"))


def test_cli_rejects_world_readable_existing_artifact(tmp_path, monkeypatch):
    import json
    import sys
    from core import mojtaba_commercial_services as engine
    source = tmp_path / "input.json"
    source.write_text(json.dumps({"service_code": "AGR-01", "data": EXAMPLES["AGR-01"]}), encoding="utf-8")
    monkeypatch.setattr(engine.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(sys, "argv", ["mojtaba-service", str(source)])
    assert engine.main() == 0
    artifact = next(tmp_path.rglob("*.md"))
    artifact.chmod(0o644)
    assert engine.main() == 2


@pytest.mark.parametrize("unsafe", ["[link](javascript:alert)", "R" + chr(92) + "bad", "audit" + chr(0x202e) + "TXT"])
def test_research_ids_reject_markup_and_directional_spoofing(unsafe):
    with pytest.raises(InvalidService):
        generate({"service_code": "RS-01", "data": {"claims": [
            {"claim_id": unsafe, "source_id": "DATA-2026", "unit": "kg_per_ha", "reproducible": True},
        ]}}, "0" * 64)


def test_existing_worker_output_must_remain_private(tmp_path):
    payload = {"service_code": "AGR-01", "data": EXAMPLES["AGR-01"]}
    with patch("core.mojtaba_commercial_services.Path.home", return_value=tmp_path):
        first = service_package(payload)
        assert first["verified_effect"] is True
        artifact = next(tmp_path.rglob("*.md"))
        artifact.chmod(0o644)
        with pytest.raises(ValueError, match="SERVICE_PACKAGE_UNSAFE_EXISTING_FILE"):
            service_package(payload)
        assert artifact.stat().st_mode & 0o077


def test_worker_refuses_hardlinked_alternate_artifact(tmp_path):
    payload = {"service_code": "AGR-01", "data": EXAMPLES["AGR-01"]}
    with patch("core.mojtaba_commercial_services.Path.home", return_value=tmp_path):
        service_package(payload)
        artifact = next(tmp_path.rglob("*.md"))
        alias = artifact.with_name("hardlink-alias.md")
        os.link(artifact, alias)
        with pytest.raises(ValueError, match="SERVICE_PACKAGE_UNSAFE_EXISTING_FILE"):
            service_package(payload)
        assert artifact.read_bytes() == alias.read_bytes()
