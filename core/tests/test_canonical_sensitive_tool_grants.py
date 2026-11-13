"""Canonical sensitive tool execution requires a bound one-shot owner grant.

These are offline database fixtures. They do not authorize production deploy,
payment, publication, live brokerage, or an external provider call.
"""

import hashlib
import json
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from core.approval import ApprovalService
from core.models import Agent, AgentCapability, AgentTask, ApprovalRequest, AuditLog
from core.tool_gateway import ToolGateway, ToolGatewayError, ToolSpec
from core.unified_bot_identity import BOT_CODE


@pytest.fixture
def sensitive_task(db):
    owner = get_user_model().objects.create_user(
        username="canonical-sensitive-grant-owner",
    )
    agent = Agent.objects.create(
        code=BOT_CODE, name="Mojtaba.bot.ai", mission="Single control plane",
        active=True,
    )
    cap = AgentCapability.objects.create(
        code="deploy", name="Owner-approved deployment",
        risk_level="high", active=True,
    )
    cap.agents.add(agent)
    task = AgentTask.objects.create(
        agent=agent, action_type="deploy", capability_code="deploy",
        risk_snapshot="high", status="running", execution_id="owner-exec-1",
        attempt_count=1, input_data={"target": "private-catalog"},
    )
    approval = ApprovalRequest.objects.create(
        action_type="deploy", target_type="AgentTask", target_id=str(task.pk),
        reason="Synthetic policy test, not a production decision",
        risk="high", status="approved", requested_by=owner,
    )
    return owner, task, approval


def reviewed_scope(task, *, tool_code="deploy", payload=None):
    planned = dict(payload if payload is not None else {"target": "private-catalog"})
    packed = json.dumps(
        planned, sort_keys=True, separators=(",", ":"),
        ensure_ascii=True, allow_nan=False,
    ).encode("utf-8")
    return {
        "action": "deploy", "agent_task_id": task.pk,
        "execution_id": task.execution_id,
        "tool_code": tool_code,
        "payload_sha256": hashlib.sha256(packed).hexdigest(),
    }


def issue_scoped_grant(owner, task, approval, scope):
    grant = ApprovalService().issue_grant(
        approval.pk, owner.pk, scope=scope, ttl_seconds=300,
    )
    task.input_data = {
        **task.input_data, "owner_approval_grant_id": grant.pk,
    }
    task.save(update_fields=["input_data", "updated_at"])
    return grant


def test_canonical_sensitive_tool_refuses_plain_approved_request(sensitive_task):
    _, task, _ = sensitive_task
    called = []
    gateway = ToolGateway([
        ToolSpec(code="deploy", risk="high", handler=lambda data: called.append(data)),
    ])
    with pytest.raises(ToolGatewayError, match="one-time owner grant"):
        gateway.invoke(
            "deploy", {"target": "private-catalog"},
            task_id=task.pk, execution_id=task.execution_id,
        )
    assert not called
    assert not AuditLog.objects.filter(action="tool_invocation_started").exists()


def test_canonical_sensitive_grant_is_consumed_and_not_forwarded(sensitive_task):
    owner, task, approval = sensitive_task
    grant = issue_scoped_grant(owner, task, approval, reviewed_scope(task))
    called = []
    gateway = ToolGateway([
        ToolSpec(
            code="deploy", risk="high",
            handler=lambda payload: called.append(payload) or {"review_only": True},
        ),
    ])
    assert gateway.invoke(
        "deploy", task.input_data, task_id=task.pk,
        execution_id=task.execution_id,
    ) == {"review_only": True}
    grant.refresh_from_db()
    assert grant.used_at is not None
    assert called == [{"target": "private-catalog"}]
    with pytest.raises(ToolGatewayError, match="already reserved"):
        gateway.invoke(
            "deploy", task.input_data, task_id=task.pk,
            execution_id=task.execution_id,
        )
    assert len(called) == 1
    assert AuditLog.objects.filter(action="tool_invocation_started").count() == 1
    assert AuditLog.objects.filter(action="approval_grant_consumed").count() == 1


def test_canonical_sensitive_grant_does_not_approve_changed_payload(sensitive_task):
    owner, task, approval = sensitive_task
    grant = issue_scoped_grant(owner, task, approval, reviewed_scope(task))
    called = []
    gateway = ToolGateway([
        ToolSpec(code="deploy", risk="high", handler=lambda data: called.append(data)),
    ])
    with pytest.raises(ToolGatewayError, match="differs from reviewed task payload"):
        gateway.invoke(
            "deploy", {"target": "external-production"},
            task_id=task.pk, execution_id=task.execution_id,
        )
    grant.refresh_from_db()
    assert grant.used_at is None
    assert not called
    assert not AuditLog.objects.filter(action="tool_invocation_started").exists()


@pytest.mark.parametrize("fault", ["wrong_digest", "expired", "used"])
def test_canonical_sensitive_grant_rejects_bad_or_consumed_scope(sensitive_task, fault):
    owner, task, approval = sensitive_task
    scope = reviewed_scope(task)
    if fault == "wrong_digest":
        scope["payload_sha256"] = "0" * 64
    grant = issue_scoped_grant(owner, task, approval, scope)
    if fault == "expired":
        grant.expires_at = timezone.now() - timedelta(seconds=1)
        grant.save(update_fields=["expires_at"])
    if fault == "used":
        grant.used_at = timezone.now()
        grant.save(update_fields=["used_at"])
    called = []
    gateway = ToolGateway([
        ToolSpec(code="deploy", risk="high", handler=lambda data: called.append(data)),
    ])
    with pytest.raises(ToolGatewayError, match="invalid, expired or consumed"):
        gateway.invoke(
            "deploy", task.input_data, task_id=task.pk,
            execution_id=task.execution_id,
        )
    assert not called
    assert not AuditLog.objects.filter(action="tool_invocation_started").exists()


def test_canonical_sensitive_grant_rejects_wrong_approval_target(sensitive_task):
    owner, task, approval = sensitive_task
    other = AgentTask.objects.create(
        agent=task.agent, action_type="deploy", capability_code="deploy",
        risk_snapshot="high", status="running", execution_id="other-exec",
        input_data={"target": "unapproved-target"},
    )
    wrong_approval = ApprovalRequest.objects.create(
        action_type="deploy", target_type="AgentTask", target_id=str(other.pk),
        reason="Other synthetic task", risk="high", status="approved",
        requested_by=owner,
    )
    grant = issue_scoped_grant(
        owner, task, wrong_approval, reviewed_scope(task),
    )
    calls = []
    gateway = ToolGateway([
        ToolSpec(code="deploy", risk="high", handler=lambda data: calls.append(data)),
    ])
    with pytest.raises(ToolGatewayError, match="matching owner approval"):
        gateway.invoke(
            "deploy", task.input_data, task_id=task.pk,
            execution_id=task.execution_id,
        )
    grant.refresh_from_db()
    assert grant.used_at is None
    assert calls == []
    assert ApprovalRequest.objects.filter(pk=approval.pk).exists()


def test_canonical_sensitive_alias_requires_its_exact_tool_scope(sensitive_task):
    owner, task, approval = sensitive_task
    grant = issue_scoped_grant(owner, task, approval, reviewed_scope(task))
    calls = []
    gateway = ToolGateway([
        ToolSpec(
            code="deploy_adapter", risk="high", allowed_actions=("deploy",),
            handler=lambda data: calls.append(data),
        ),
    ])
    with pytest.raises(ToolGatewayError, match="invalid, expired or consumed"):
        gateway.invoke(
            "deploy_adapter", task.input_data,
            task_id=task.pk, execution_id=task.execution_id,
        )
    grant.refresh_from_db()
    assert grant.used_at is None
    assert not calls
    # Another explicitly issued one-shot grant matches the actual adapter.
    second = issue_scoped_grant(
        owner, task, approval, reviewed_scope(task, tool_code="deploy_adapter"),
    )
    gateway.invoke(
        "deploy_adapter", task.input_data,
        task_id=task.pk, execution_id=task.execution_id,
    )
    second.refresh_from_db()
    assert second.used_at is not None
    assert calls == [{"target": "private-catalog"}]
