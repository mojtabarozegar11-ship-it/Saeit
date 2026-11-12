"""Approved chat-operation executor.

This module is deliberately narrower than a shell. It executes only named
operations produced by operation_planner and records evidence in AuditLog.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from django.db import transaction

from command_center.models import MpwRecord, TENANT
from .models import ApprovalRequest, AuditLog
from .chat_operation_security import is_authorized_chat_operator
from .newsletter_models import NewsletterSubmission


def _root() -> Path:
    for candidate in (Path("/home/zomorod2/Saeit"), Path("/home/zomorodm/repositories/Saeit")):
        if (candidate / "manage.py").is_file():
            return candidate
    return Path.cwd()


def _audit_exists(approval_id: int) -> bool:
    return AuditLog.objects.filter(
        action="chat_operation_executed",
        target_type="ApprovalRequest",
        target_id=str(approval_id),
    ).exists()


def _run_readonly(action: str) -> dict:
    root = _root()
    if action == "cpanel.preflight":
        command = ["bash", str(root / "scripts/cpanel_preflight.sh"), str(root)]
    elif action == "cpanel.passenger_inventory":
        command = ["uapi", "--output=json", "PassengerApps", "list_applications"]
    else:
        raise ValueError("unsupported_readonly_cpanel_action")
    result = subprocess.run(
        command, cwd=str(root), text=True, capture_output=True, timeout=120, check=False
    )
    output = (result.stdout or "")[-12000:]
    error = (result.stderr or "")[-4000:]
    return {"returncode": result.returncode, "stdout": output, "stderr": error}


def _perform_chat_action(approval: ApprovalRequest) -> tuple[str, dict, dict]:
    data = json.loads(approval.reason)
    action = data["action"]
    params = data.get("parameters") or {}
    target = data.get("target", "")
    result: dict

    if action == "site.create_draft_page":
        path = str(params["path"])
        title = str(params["title"])[:200]
        body = str(params.get("body", ""))[:4000]
        if target == "mojplaywin":
            key = "chat-" + data["operation_id"]
            record = MpwRecord.objects.create(
                tenant=TENANT, kind="content", key=key, page_path=path,
                title=title, draft={"content": body, "source": "staff_chat"},
                state="draft",
            )
            result = {"site": target, "record_id": record.pk, "state": record.state, "path": record.page_path}
        elif target == "zomorodmelal":
            if not path.startswith("/company/"):
                raise ValueError("zomorod_target_must_be_company_path")
            submission = NewsletterSubmission.objects.create(
                subject=title,
                body=body,
                status="queued",
                created_by=approval.requested_by,
                company_target_paths=path,
                company_activity_status="آینده",
            )
            result = {"site": target, "submission_id": submission.pk, "state": submission.status, "path": path}
        else:
            raise ValueError("site_target_not_implemented")
    elif action == "site.update_draft_page":
        path = str(params["path"])
        instruction = str(params["instruction"])[:4000]
        if target == "mojplaywin":
            record = MpwRecord.objects.filter(
                tenant=TENANT, page_path=path
            ).order_by("-updated_at").first()
            if record is None:
                raise ValueError("draft_page_not_found")
            before = dict(record.draft)
            record.draft = {**before, "chat_instruction": instruction}
            record.revision += 1
            record.state = "draft"
            record.save(update_fields=["draft", "revision", "state", "updated_at"])
            result = {"site": target, "record_id": record.pk, "state": record.state, "revision": record.revision}
        elif target == "zomorodmelal":
            if not path.startswith("/company/"):
                raise ValueError("zomorod_target_must_be_company_path")
            submission = NewsletterSubmission.objects.create(
                subject="ویرایش محتوای " + path,
                body=instruction,
                status="queued",
                created_by=approval.requested_by,
                company_target_paths=path,
                company_activity_status="مطالعه",
            )
            result = {"site": target, "submission_id": submission.pk, "state": submission.status, "path": path}
        else:
            raise ValueError("site_target_not_implemented")
    elif action in {"cpanel.preflight", "cpanel.passenger_inventory"}:
        result = _run_readonly(action)
    elif action == "cpanel.deploy_release":
        root = _root()
        result_proc = subprocess.run(
            ["bash", str(root / "deploy/cpanel_deploy.sh")],
            cwd=str(root), text=True, capture_output=True, timeout=600, check=False
        )
        result = {"returncode": result_proc.returncode,
                  "stdout": (result_proc.stdout or "")[-12000:],
                  "stderr": (result_proc.stderr or "")[-4000:]}
    else:
        raise ValueError("unsupported_chat_operation")
    if isinstance(result, dict) and result.get("returncode", 0) != 0:
        raise RuntimeError("chat_operation_command_failed")
    return action, data, result


def execute_approved_chat_operation(approval: ApprovalRequest) -> dict:
    """Claim exactly one execution attempt before any external side effect.

    A crash or timeout after claiming remains closed to automatic retries;
    staff must reconcile the outcome explicitly before any new request.
    """
    with transaction.atomic():
        locked = (
            ApprovalRequest.objects.select_for_update()
            .select_related("requested_by")
            .get(pk=approval.pk)
        )
        if locked.target_type != "ChatOperation":
            raise ValueError("not_chat_operation")
        if not is_authorized_chat_operator(locked.requested_by):
            raise PermissionError("chat_operation_requires_active_superuser")
        if locked.status in {"executing", "executed", "execution_failed"}:
            return {
                "status": (
                    "already_executed" if locked.status == "executed"
                    else "execution_in_progress" if locked.status == "executing"
                    else "manual_reconciliation_required"
                ),
                "approval_id": locked.pk,
            }
        if locked.status != "approved":
            raise ValueError("approval_not_approved")
        if _audit_exists(locked.pk):
            locked.status = "executed"
            locked.save(update_fields=["status", "updated_at"])
            return {"status": "already_executed", "approval_id": locked.pk}
        locked.status = "executing"
        locked.save(update_fields=["status", "updated_at"])

    try:
        action, data, result = _perform_chat_action(locked)
    except Exception as exc:
        # The side effect may have completed before an exception was raised.
        # Never retry this approval automatically, even when its outcome is unknown.
        with transaction.atomic():
            ApprovalRequest.objects.filter(pk=locked.pk, status="executing").update(
                status="execution_failed",
                decision_note="manual_reconciliation_required:" + type(exc).__name__,
            )
            AuditLog.objects.create(
                actor_type="owner_approved_chat",
                actor_id=str(locked.requested_by_id),
                action="chat_operation_execution_failed",
                target_type="ApprovalRequest",
                target_id=str(locked.pk),
                after_state={"error_type": type(exc).__name__, "requires_reconciliation": True},
                trace_id="chat-operation-failed-" + str(locked.pk),
            )
        raise

    with transaction.atomic():
        updated = ApprovalRequest.objects.filter(pk=locked.pk, status="executing").update(
            status="executed", decision_note="execution_completed"
        )
        if updated != 1:
            raise RuntimeError("chat_operation_claim_lost")
        AuditLog.objects.create(
            actor_type="owner_approved_chat",
            actor_id=str(locked.requested_by_id),
            action="chat_operation_executed",
            target_type="ApprovalRequest",
            target_id=str(locked.pk),
            after_state={"operation_id": data["operation_id"], "action": action, "result": result},
            trace_id="chat-operation-" + data["operation_id"],
        )
    return {"status": "executed", "approval_id": locked.pk, "action": action, "result": result}
