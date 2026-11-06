"""Deterministic allowlist for actions requested through ordinary staff chat.

The language model may explain an action, but it cannot invent an executable
shell command. Only these structured operations can enter the approval queue.
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ChatOperation:
    operation_id: str
    action: str
    target: str
    parameters: dict[str, Any]
    risk: str
    approval_required: bool = True


def _path(text: str) -> str | None:
    match = re.search(r"(?P<path>/[A-Za-z0-9_./-]{1,180})", text)
    return match.group("path") if match else None


def _quoted(text: str) -> str | None:
    match = re.search(r'[«"“](.{1,240}?)[»"”]', text)
    return match.group(1).strip() if match else None


def plan_chat_operation(text: str) -> ChatOperation | None:
    """Return a bounded operation only for explicit operational language."""
    raw = str(text or "").strip()
    low = raw.casefold()
    operation_id = uuid.uuid4().hex

    if any(word in low for word in ("پیش‌بررسی cpanel", "preflight cpanel", "cpanel preflight")):
        return ChatOperation(operation_id, "cpanel.preflight", "cPanel", {}, "medium")

    if any(word in low for word in ("فهرست passenger", "passenger inventory", "مسیرهای passenger")):
        return ChatOperation(operation_id, "cpanel.passenger_inventory", "cPanel", {}, "medium")

    if any(word in low for word in ("انتشار نسخه", "deploy release", "انتشار سایت", "deploy سایت")):
        return ChatOperation(operation_id, "cpanel.deploy_release", "cPanel", {}, "critical")

    if any(word in low for word in ("صفحه جدید", "صفحه تازه", "صفحه اضافه", "create page", "add page")):
        path = _path(raw) or "/"
        title = _quoted(raw) or ""
        if not title:
            title_match = re.search(r"(?:صفحه|page)\s+([^/]{2,120})", raw, re.I)
            title = title_match.group(1).strip(" .،,") if title_match else ""
        if not title:
            return None
        target = "zomorodmelal" if any(x in low for x in ("زمرد", "zomorod")) else "mojplaywin"
        return ChatOperation(
            operation_id, "site.create_draft_page", target,
            {"path": path, "title": title[:200], "body": raw[:4000]}, "high"
        )

    if any(word in low for word in ("محتوای صفحه", "ویرایش صفحه", "update page", "edit page")):
        path = _path(raw)
        if not path:
            return None
        target = "zomorodmelal" if any(x in low for x in ("زمرد", "zomorod")) else "mojplaywin"
        return ChatOperation(
            operation_id, "site.update_draft_page", target,
            {"path": path, "instruction": raw[:4000]}, "high"
        )

    return None


def approval_reason(operation: ChatOperation) -> str:
    import json
    return json.dumps({
        "operation_id": operation.operation_id,
        "action": operation.action,
        "target": operation.target,
        "parameters": operation.parameters,
    }, ensure_ascii=False, sort_keys=True)
