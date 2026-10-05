import hashlib
import hmac
import json
import os
import time
import uuid

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .models import AgentTask, AuditLog


def _secret():
    return os.getenv("SAEIT_BRIDGE_SECRET", "").encode("utf-8")


def _authorized(request, raw_body=b""):
    secret = _secret()
    if not secret:
        return False, "bridge_not_configured"

    timestamp = request.headers.get("X-Saeit-Timestamp", "")
    signature = request.headers.get("X-Saeit-Signature", "")
    try:
        ts = int(timestamp)
    except (TypeError, ValueError):
        return False, "invalid_timestamp"
    if abs(int(time.time()) - ts) > 300:
        return False, "expired_request"
    expected = hmac.new(
        secret, timestamp.encode("utf-8") + b"." + raw_body, hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return False, "invalid_signature"
    return True, "hmac"


def _audit(action, *, target_id="", after_state=None, trace_id=""):
    AuditLog.objects.create(
        actor_type="control-bridge",
        actor_id="external-controller",
        action=action,
        target_type="AgentTask",
        target_id=str(target_id or ""),
        after_state=after_state or {},
        trace_id=trace_id or f"bridge-{uuid.uuid4().hex}",
    )


@require_GET
def bridge_health(request):
    configured = bool(_secret())
    return JsonResponse({
        "status": "ok" if configured else "degraded",
        "service": "saeit-control-bridge",
        "configured": configured,
        "auth": "hmac-sha256",
        "owner_approval": True,
        "execution": "task_queue_only",
    }, status=200 if configured else 503)


@csrf_exempt
@require_POST
def bridge_dispatch(request):
    raw = request.body or b""
    allowed, auth_mode = _authorized(request, raw)
    if not allowed:
        return JsonResponse({"status": "denied", "reason": auth_mode}, status=401)
    try:
        payload = json.loads(raw.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JsonResponse({"status": "error", "reason": "invalid_json"}, status=400)

    # The public bridge deliberately has no arbitrary shell/cPanel/deploy primitive.
    # It can only enqueue an already-registered capability for an active agent.
    action = str(payload.get("action", "")).strip().lower().replace("-", "_").replace(" ", "_")
    request_data = payload.get("request", {})
    if not action or not isinstance(request_data, dict):
        return JsonResponse({"status": "error", "reason": "valid_action_and_request_required"}, status=400)

    from .agent_registry import AgentRegistry
    registry = AgentRegistry()
    agent = registry.resolve(action)
    capability = registry.capability_for(agent, action) if agent else None
    if not agent or not capability:
        trace_id = f"bridge-{uuid.uuid4().hex}"
        _audit("bridge_dispatch_rejected", after_state={"action": action, "reason": "unregistered_capability"}, trace_id=trace_id)
        return JsonResponse({"status": "denied", "reason": "unregistered_capability", "trace_id": trace_id}, status=403)

    effective_risk = registry.effective_risk(capability, str(payload.get("risk", "low")))
    from .services import requires_owner_approval
    approval_required = requires_owner_approval(action, effective_risk)
    if approval_required:
        trace_id = f"bridge-{uuid.uuid4().hex}"
        _audit("bridge_dispatch_rejected", after_state={"action": action, "reason": "owner_approval_required", "risk": effective_risk}, trace_id=trace_id)
        return JsonResponse({
            "status": "denied", "reason": "owner_approval_required",
            "risk": effective_risk, "trace_id": trace_id,
        }, status=403)
    task = AgentTask.objects.create(
        agent=agent,
        action_type=action,
        capability_code=capability.code,
        risk_snapshot=effective_risk,
        input_data={
            **request_data,
            "bridge": {"source": "authenticated_control_bridge", "auth_mode": auth_mode},
        },
        status="blocked" if approval_required else "queued",
    )
    trace_id = f"bridge-task-{task.pk}-{uuid.uuid4().hex[:12]}"
    _audit(
        "bridge_task_created",
        target_id=task.pk,
        after_state={
            "action": action,
            "agent": agent.code,
            "risk": effective_risk,
            "status": task.status,
            "approval_required": approval_required,
        },
        trace_id=trace_id,
    )
    return JsonResponse({
        "status": "queued",
        "task_id": task.pk,
        "action": action,
        "agent": agent.code,
        "risk": effective_risk,
        "approval_required": approval_required,
        "trace_id": trace_id,
        "execution": "worker_runner",
    }, status=202)
