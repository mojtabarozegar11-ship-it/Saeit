"""The DB master must really execute and audit six evidence-bound native tasks."""
import importlib.util
import json
from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from core.factory_native_review_gateway import ACTION, FAMILIES, inspect_family
from core.models import Agent, AgentTask, AuditLog


def import_from(path, module_name):
    s=importlib.util.spec_from_file_location(module_name,str(path))
    m=importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


@pytest.fixture
def private_factory(tmp_path, monkeypatch):
    root=tmp_path/"factory-runtime"/"private"/"autonomous-product-cycle"
    root.mkdir(parents=True)
    repo=Path(__file__).resolve().parents[2]
    source=import_from(repo/"tests"/"test_factory_six_native_independent_rework.py",
                       "master_six_test_fixtures")
    reviewer=import_from(repo/"scripts"/"factory_six_native_independent_rework.py",
                         "master_six_reviewer")
    source.fixtures(root,labelled_accessibility=True)
    reviewer.run(root,"39714521227-1")
    monkeypatch.setattr(Path,"home",classmethod(lambda cls:tmp_path))
    monkeypatch.setenv("MOJ_FACTORY_LOCAL_MODE","1")
    return root


@pytest.mark.django_db
def test_real_master_six_agent_tasks_are_claimed_and_audited(private_factory):
    call_command("seed_online_income_agents",verbosity=0)
    call_command("factory_native_enqueue",execute=True,verbosity=0)
    agent=Agent.objects.get(code="moj_1ro_1",active=True)
    economic=Agent.objects.get(code="economic-master-agent",active=True)
    assert not economic.capabilities.filter(code=ACTION,active=True).exists()
    assert set(agent.capabilities.filter(active=True).values_list("code",flat=True))=={ACTION}
    assert agent.capabilities.filter(code=ACTION,active=True).exists()
    tasks=list(AgentTask.objects.filter(agent=agent,action_type=ACTION).order_by("pk"))
    assert len(tasks)==6
    assert {t.input_data["family"] for t in tasks}==set(FAMILIES)
    assert all(t.status=="completed" and t.execution_id and t.attempt_count==1
               for t in tasks)
    assert all(t.output_data["verified_effect"] is True and
               t.output_data["master_verified_task_execution"] is True and
               t.output_data["quality_1000_certified"] is False and
               t.output_data["commercial_release"] is False for t in tasks)
    assert AuditLog.objects.filter(action="tool_invocation_completed",target_type="AgentTask",
                                  target_id__in=[str(t.pk) for t in tasks]).count()==6
    call_command("factory_native_enqueue",execute=True,verbosity=0)
    assert AgentTask.objects.filter(agent=agent,action_type=ACTION).count()==6


@pytest.mark.django_db
def test_forged_native_1000_receipt_cannot_execute(private_factory):
    call_command("seed_online_income_agents",verbosity=0)
    folder=private_factory/"native-candidate-evidence"/"39714521227-1"/"F12"
    receipt=folder/"technical-native-receipt.json"
    d=json.loads(receipt.read_text())
    d["quality_1000_certified"]=True
    receipt.write_text(json.dumps(d))
    with pytest.raises(CommandError):
        call_command("factory_native_enqueue",execute=True,verbosity=0)
    assert not AgentTask.objects.filter(action_type=ACTION).exists()


@pytest.mark.django_db
def test_worker_rejects_mismatched_receipt_version(private_factory):
    call_command("seed_online_income_agents",verbosity=0)
    base=private_factory/"quality-excellence"/"six-native-rework"/"39714521227-1"
    import hashlib
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    good={
        "source_run":"39714521227-1",
        "family":"F17",
        "review_sha256":sha(base/"review.json"),
        "family_receipt_sha256":sha(base/"F17.json")
    }
    result=inspect_family(private_factory,good)
    assert result["verified_effect"] is True
    assert result["pending_external_specialist_gates"]
    assert result["quality_1000_certified"] is False
    bad=dict(good,review_sha256="0"*64)
    with pytest.raises(ValueError,match="SOURCE_VERSION_CHANGED"):
        inspect_family(private_factory,bad)
    assert not AgentTask.objects.filter(action_type=ACTION).exists()
