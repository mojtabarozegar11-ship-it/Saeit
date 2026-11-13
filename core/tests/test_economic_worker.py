import os
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from core.economic_tool_pack import build_mvp_asset, offer_design
from core.models import Agent, AgentTask, Product


@pytest.mark.django_db
def test_worker_executes_first_self_improvement_task_with_verified_evidence(monkeypatch):
    monkeypatch.setenv("MOJ_FACTORY_LOCAL_MODE", "1")
    call_command("seed_online_income_agents")
    call_command("online_income_cycle")
    call_command("run_economic_worker")

    task = AgentTask.objects.get(capability_code="master_self_improvement")
    assert task.status == "completed"
    assert task.output_data["verified_effect"] is True
    assert task.output_data["action_performed"]
    assert task.output_data["evidence"]["kind"] == "private_self_upgrade_dossier"
    assert task.output_data["production_promotion"] is False


def test_master_self_improvement_rejects_invalid_dossier_in_primary_runtime(monkeypatch, tmp_path):
    """No task can claim verified effect if the candidate dossier fails inspection."""
    from core import isolated_upgrade_proof
    from core.economic_tool_pack import master_self_improvement

    monkeypatch.setenv("MOJ_FACTORY_LOCAL_MODE", "1")
    monkeypatch.setenv("HOME", str(tmp_path))

    def reject_tampered_candidate(_path, *, source_root=None):
        raise ValueError("ISOLATED_UPGRADE_PROOF_CANDIDATE_HASH_MISMATCH")

    monkeypatch.setattr(isolated_upgrade_proof, "inspect_isolated_proof",
                        reject_tampered_candidate)
    with pytest.raises(ValueError, match="CANDIDATE_HASH_MISMATCH"):
        master_self_improvement({})


def test_master_self_improvement_has_verified_manifest_but_no_live_promotion(monkeypatch, tmp_path):
    from core.economic_tool_pack import master_self_improvement

    monkeypatch.setenv("MOJ_FACTORY_LOCAL_MODE", "1")
    monkeypatch.setenv("HOME", str(tmp_path))
    result = master_self_improvement({})
    assert result["verified_effect"] is True
    assert result["production_promotion"] is False
    assert "proof_sha256" in result["evidence"]["value"]
    assert "candidate_artifacts_hash_verified" in result["evidence"]["value"]


@pytest.mark.django_db
def test_cycle_advances_from_self_improvement_to_verified_market_research(monkeypatch):
    monkeypatch.setenv("MOJ_FACTORY_LOCAL_MODE", "1")
    call_command("seed_online_income_agents")
    call_command("online_income_cycle")
    call_command("run_economic_worker")
    call_command("online_income_cycle")

    tasks = list(AgentTask.objects.order_by("created_at"))
    assert len(tasks) == 2
    assert tasks[0].capability_code == "master_self_improvement"
    assert tasks[0].status == "completed"
    assert tasks[1].capability_code == "income_market_research"
    assert tasks[1].status == "queued"


@pytest.mark.django_db
@pytest.mark.parametrize("drain,expected", [(False, 1), (True, 20)])
def test_economic_worker_bounded_drain_never_repeats_a_task(drain, expected):
    agent, _ = Agent.objects.update_or_create(
        code="economic-master-agent",
        defaults={"name": "Master", "mission": "Verified economic actions", "active": True},
    )
    tasks = AgentTask.objects.bulk_create([
        AgentTask(agent=agent, action_type="income_market_research",
                  capability_code="income_market_research", status="queued")
        for _ in range(21)
    ])
    executed_ids = []

    def safe_fake_run(task_id):
        executed_ids.append(task_id)
        AgentTask.objects.filter(pk=task_id).update(status="completed")
        return SimpleNamespace(pk=task_id, status="completed",
                               output_data={"action_performed": "verified_action"})

    gateway = SimpleNamespace(describe=lambda: {"income_market_research": {}})
    with patch("core.management.commands.run_economic_worker.build_economic_gateway",
               return_value=gateway), patch(
                   "core.management.commands.run_economic_worker.WorkerRunner"
               ) as runner:
        runner.return_value.run.side_effect = safe_fake_run
        output = StringIO()
        call_command("run_economic_worker", *("--drain",) if drain else (),
                     stdout=output)

    assert len(executed_ids) == expected
    assert len(set(executed_ids)) == expected
    assert set(executed_ids).issubset({task.pk for task in tasks})
    assert AgentTask.objects.filter(agent=agent, status="queued").count() == 21 - expected
    if drain:
        assert "DRAIN_SUMMARY completed=20 limit=20" in output.getvalue()
    else:
        assert "DRAIN_SUMMARY" not in output.getvalue()


def test_mvp_builder_writes_private_verified_customer_workbook(tmp_path):
    asset = build_mvp_asset(321, "Digital Project & Automation Audit", root=tmp_path)
    path = Path(asset["relative_path"])

    assert path.is_file()
    assert os.stat(path).st_mode & 0o777 == 0o600
    assert asset["quality_gate"] == "passed"
    assert asset["section_count"] == 10
    assert asset["checklist_items"] == 50
    assert asset["bytes"] > 7000
    document = path.read_text(encoding="utf-8")
    assert "Evidence register" in document
    assert "30-day action plan" in document
    assert "Launch gate" in document
    assert "Digital Project &amp; Automation Audit" in document
    assert "commercial_release" not in document


@pytest.mark.django_db
def test_offer_design_creates_isolated_inactive_draft_without_relabeling_catalog():
    existing = Product.objects.create(
        title="Existing customer workbook", product_type="book", price="12.00",
        currency="USD", active=False, metadata={"custom": "preserve"},
    )

    result = offer_design({})

    existing.refresh_from_db()
    draft = Product.objects.get(metadata__commercial_status="offer_designed")
    assert existing.title == "Existing customer workbook"
    assert existing.metadata == {"custom": "preserve"}
    assert draft.title == "Digital Project & Automation Audit"
    assert draft.product_type == "service"
    assert draft.active is False
    assert draft.price == 0
    assert draft.metadata["pricing_status"] == "requires_market_evidence"
    assert result["evidence"]["kind"] == "product_record"
    assert str(draft.pk) in result["evidence"]["value"]


@pytest.mark.parametrize("command,kwargs", [
    ("economic_worker", {"limit": 0}),
    ("economic_worker", {"limit": 21}),
    ("run_economic_worker", {"limit": -1}),
    ("run_economic_worker", {"drain": True, "limit": 4}),
    ("run_economic_worker", {"task_id": -3}),
])
def test_all_economic_worker_entry_points_enforce_bounded_execution(command, kwargs):
    with pytest.raises(CommandError):
        call_command(command, **kwargs)


@pytest.mark.django_db
def test_legacy_worker_is_a_single_controlled_dispatcher_and_requires_active_agent():
    agent = Agent.objects.create(
        code="economic-master-agent", name="Master", mission="Economic tasks", active=False
    )
    tasks = AgentTask.objects.bulk_create([
        AgentTask(agent=agent, action_type="income_market_research",
                  capability_code="income_market_research", status="queued")
        for _ in range(3)
    ])
    output = StringIO()
    call_command("economic_worker", limit=3, stdout=output)
    assert "IDLE: no active canonical bot runtime." in output.getvalue()
    assert AgentTask.objects.filter(agent=agent, status="queued").count() == 3

    agent.active = True
    agent.save(update_fields=["active"])
    completed_ids = []

    def complete(task_id):
        completed_ids.append(task_id)
        AgentTask.objects.filter(pk=task_id).update(status="completed")
        return SimpleNamespace(pk=task_id, status="completed", output_data={
            "action_performed": "internal_inspection", "verified_effect": True,
        })

    gateway = SimpleNamespace(describe=lambda: {"income_market_research": {}})
    with patch("core.management.commands.run_economic_worker.build_economic_gateway",
               return_value=gateway), patch(
                   "core.management.commands.run_economic_worker.WorkerRunner"
               ) as runner:
        runner.return_value.run.side_effect = complete
        output = StringIO()
        call_command("economic_worker", limit=3, stdout=output)

    assert set(completed_ids) == {task.pk for task in tasks}
    assert "revenue_not_assessed=true" in output.getvalue()


@pytest.mark.django_db
def test_worker_skips_unregistered_income_tool_without_consuming_attempts():
    agent = Agent.objects.create(
        code="economic-master-agent", name="Master", mission="Bounded work", active=True,
    )
    unsupported = AgentTask.objects.create(
        agent=agent, action_type="income_unregistered_external_post",
        capability_code="income_unregistered_external_post", status="queued",
    )
    supported = AgentTask.objects.create(
        agent=agent, action_type="income_market_research",
        capability_code="income_market_research", status="queued",
    )

    def complete(task_id):
        AgentTask.objects.filter(pk=task_id).update(status="completed")
        return SimpleNamespace(pk=task_id, status="completed", output_data={"verified_effect": True})

    gateway = SimpleNamespace(describe=lambda: {"income_market_research": {"enabled": True}})
    with patch("core.management.commands.run_economic_worker.build_economic_gateway",
               return_value=gateway), patch(
                   "core.management.commands.run_economic_worker.WorkerRunner"
               ) as runner:
        runner.return_value.run.side_effect = complete
        output = StringIO()
        call_command("run_economic_worker", limit=2, stdout=output)
        runner.return_value.run.assert_called_once_with(supported.pk)

    unsupported.refresh_from_db()
    supported.refresh_from_db()
    assert supported.status == "completed"
    assert unsupported.status == "queued"
    assert unsupported.attempt_count == 0
    assert "completed=1" not in output.getvalue()  # only --drain prints a summary


@pytest.mark.django_db
def test_worker_reports_unknown_only_queue_without_executing():
    agent = Agent.objects.create(
        code="economic-master-agent", name="Master", mission="Bounded work", active=True,
    )
    unsupported = AgentTask.objects.create(
        agent=agent, action_type="income_missing_tool", capability_code="income_missing_tool",
        status="queued",
    )
    with patch("core.management.commands.run_economic_worker.WorkerRunner") as runner:
        output = StringIO()
        call_command("run_economic_worker", stdout=output)
        runner.assert_not_called()
    unsupported.refresh_from_db()
    assert unsupported.attempt_count == 0
    assert unsupported.status == "queued"
    assert "BLOCKED_UNSUPPORTED" in output.getvalue()
