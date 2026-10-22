"""F41 private products must be executed by the real audited master AgentTask runtime."""
import json
import shutil
from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from core.models import Agent, AgentTask, AuditLog
from core.factory_f41_gateway import ACTION

KINDS = ("vesting", "reconciliation", "provenance", "nft_metadata")


@pytest.fixture
def private_f41(tmp_path, monkeypatch):
    project = Path(__file__).resolve().parents[2]
    root = tmp_path / "factory-runtime"
    operations = root / "operations" / "f41-multiproduct"
    private = root / "private" / "autonomous-product-cycle" / "f41-multiproduct"
    (operations / "assets").mkdir(parents=True)
    (private / "orders").mkdir(parents=True)
    (private / "outputs").mkdir()
    shutil.copy2(project / "scripts" / "factory_f41_multi_product_builder.py",
                 operations / "factory_f41_multi_product_builder.py")
    for name in ("demo_art.svg", "license_terms.txt"):
        shutil.copy2(project / "factory_assets" / "f41_demo_assets" / name,
                     operations / "assets" / name)
    for kind in KINDS:
        shutil.copy2(project / "factory_config" / "f41_samples" / (kind + ".json"),
                     private / "orders" / ("F41-pilot-" + kind.replace("_", "-") + ".json"))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setenv("MOJ_FACTORY_LOCAL_MODE", "1")
    return private


@pytest.mark.django_db
def test_private_queue_builds_all_four_with_real_master_and_audits(private_f41):
    call_command("seed_online_income_agents", verbosity=0)
    call_command("factory_f41_enqueue", dry_run=True, verbosity=0)
    assert not AgentTask.objects.filter(action_type=ACTION).exists()
    call_command("factory_f41_enqueue", execute=True, verbosity=0)
    master = Agent.objects.get(code="moj_1ro_1", active=True)
    economic = Agent.objects.get(code="economic-master-agent", active=True)
    assert set(master.capabilities.values_list("code", flat=True)) == {
        "factory_native_review", ACTION}
    assert not economic.capabilities.filter(code=ACTION).exists()
    tasks = list(AgentTask.objects.filter(agent=master, action_type=ACTION))
    assert len(tasks) == 4
    assert {x.output_data["kind"] for x in tasks} == set(KINDS)
    assert all(x.status == "completed" and x.execution_id and
               x.output_data["verified_effect"] is True and
               x.output_data["quality_1000_certified"] is False and
               x.output_data["commercial_release"] is False and
               x.output_data["mainnet_transactions"] == 0 for x in tasks)
    assert AuditLog.objects.filter(action="tool_invocation_completed",
        target_type="AgentTask", target_id__in=[str(t.pk) for t in tasks]).count() == 4
    call_command("factory_f41_enqueue", execute=True, verbosity=0)
    assert AgentTask.objects.filter(action_type=ACTION).count() == 4
    for t in tasks:
        assert (private_f41 / "outputs" / t.input_data["order_id"] /
                "manifest.json").is_file()


@pytest.mark.django_db
def test_mutated_order_fails_without_reusing_verified_task(private_f41):
    call_command("seed_online_income_agents", verbosity=0)
    call_command("factory_f41_enqueue", execute=True, verbosity=0)
    target = private_f41 / "orders" / "F41-pilot-vesting.json"
    data = json.loads(target.read_text())
    data["product_id"] = "new-id-attempt"
    target.write_text(json.dumps(data))
    with pytest.raises(CommandError, match="CHANGED_ORDER"):
        call_command("factory_f41_enqueue", execute=True, verbosity=0)
    assert AgentTask.objects.filter(action_type=ACTION).count() == 4


def test_gateway_ignores_nonbinding_runtime_metadata(private_f41):
    from core.factory_f41_gateway import inspect_order, roots, build_verified_order
    root, ops = roots()
    payload = inspect_order(root, ops, "F41-pilot-vesting")
    payload["runtime_context"] = {"execution_id": "inject", "external_destination": "/tmp/unsafe"}
    result = build_verified_order(payload)
    assert result["verified_effect"] is True
    assert result["financial_actions"] == 0
    assert result["commercial_release"] is False


@pytest.mark.django_db
def test_symlink_and_forged_receipt_fail_closed(private_f41):
    call_command("seed_online_income_agents", verbosity=0)
    target = private_f41 / "orders" / "F41-pilot-nft-metadata.json"
    target.unlink()
    target.symlink_to(private_f41 / "orders" / "F41-pilot-vesting.json")
    with pytest.raises(CommandError, match="PREFLIGHT_FAILED"):
        call_command("factory_f41_enqueue", execute=True, verbosity=0)
    assert AgentTask.objects.filter(action_type=ACTION).count() == 0
