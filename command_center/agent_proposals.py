"""Propose an agent change without applying it or granting execution authority."""
import json
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from core.models import Agent, ApprovalRequest

ALLOWED_FIELDS = {"mission", "active", "risk_level"}

@staff_member_required
@require_POST
def propose(request):
    try:
        payload = json.loads(request.body)
        agent_id = int(payload["agent_id"])
        field = payload["field"]
        value = payload["value"]
        if field not in ALLOWED_FIELDS:
            return JsonResponse({"error": "unsupported_field"}, status=400)
        if field == "active" and type(value) is not bool:
            return JsonResponse({"error": "invalid_value"}, status=400)
        if field == "mission" and (not isinstance(value, str) or not 1 <= len(value) <= 4000):
            return JsonResponse({"error": "invalid_value"}, status=400)
        if field == "risk_level" and value not in ("low", "medium", "high"):
            return JsonResponse({"error": "invalid_value"}, status=400)
        agent = Agent.objects.get(pk=agent_id)
    except (ValueError, TypeError, KeyError, json.JSONDecodeError, Agent.DoesNotExist):
        return JsonResponse({"error": "invalid_request"}, status=400)
    approval = ApprovalRequest.objects.create(
        action_type="agent_configuration_proposal",
        target_type="agent",
        target_id=str(agent.pk),
        reason=json.dumps({"field": field, "proposed_value": value}, ensure_ascii=False),
        risk="high",
        status="pending",
        requested_by=request.user,
    )
    response = JsonResponse({"approval_id": approval.pk, "status": "pending", "applied": False}, status=201)
    response["Cache-Control"] = "no-store"
    return response
