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
from django.utils import timezone

from command_center.models import MpwRecord, TENANT
from .models import ApprovalRequest, AuditLog
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


@transaction.atomic
def execute_approved_chat_operation(approval: ApprovalRequest) -> dict:
    if approval.status != "approved":
        raise ValueError("approval_not_approved")
    if approval.target_type != "ChatOperation":
        raise ValueError("not_chat_operation")
    if _audit_exists(approval.pk):
        return {"status": "already_executed", "approval_id": approval.pk}

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

    AuditLog.objects.create(
        actor_type="owner_approved_chat",
        actor_id=str(approval.requested_by_id),
        action="chat_operation_executed",
        target_type="ApprovalRequest",
        target_id=str(approval.pk),
        after_state={"operation_id": data["operation_id"], "action": action, "result": result},
        trace_id="chat-operation-" + data["operation_id"],
    )
    return {"status": "executed", "approval_id": approval.pk, "action": action, "result": result}
