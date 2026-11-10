import os

from openai import OpenAI

from .models import ChatMessage
from .master_agent_capability_pack import MASTER_AGENT_CAPABILITY_PACK, capability_pack_prompt
from .chat_operation_security import is_authorized_chat_operator
from .cyber_defense import make_security_event, seal_evidence, triage_security_events


SYSTEM_PROMPT = """
You are the Master Agent assistant for Saeit.
You are a controlled management and research assistant.
Explain plans, research tasks, risks, and required approvals clearly.
Never claim that an action was executed when it was only discussed.
Never perform or authorize sensitive actions such as deployment, payments,
external writes, deletion, legal actions, or production changes without
an explicit owner approval recorded by the backend.
Keep responses concise and operational.
"""


def master_system_prompt():
    return SYSTEM_PROMPT.strip() + "\n\n" + capability_pack_prompt()


class MasterAgentChat:
    def respond(self, session, user_text):
        text = str(user_text or "").strip()
        if not text:
            raise ValueError("Message cannot be empty")

        ChatMessage.objects.create(session=session, role="user", content=text)

        # Explicit operational language becomes a structured operation.
        # The owner chat executes synchronously; all other users remain queued
        # behind the existing approval lifecycle.
        from .operation_planner import approval_reason, plan_chat_operation
        from .models import ApprovalRequest, AuditLog

        operation = plan_chat_operation(text)
        if operation is not None:
            direct_owner = is_authorized_chat_operator(session.user)
            if not direct_owner:
                denied_event = make_security_event(
                    "privileged_action_denied", "master_agent_chat",
                    actor_id=str(session.user.pk),
                )
                denied_assessment = triage_security_events([denied_event])
                AuditLog.objects.create(
                    actor_type="authenticated_chat_user",
                    actor_id=str(session.user.pk),
                    action="privileged_chat_operation_denied",
                    target_type="ChatOperation",
                    target_id=operation.operation_id,
                    after_state={
                        "security_event": denied_event,
                        "severity": denied_assessment["severity"],
                        "evidence_hash": seal_evidence(denied_event)["record_hash"],
                    },
                    trace_id="chat-operation-denied-" + operation.operation_id,
                )
                reply = "اجرای دستور مدیریتی از این حساب مجاز نیست؛ فقط مدیر ارشد فعال می‌تواند دستور عملیاتی صادر کند."
                ChatMessage.objects.create(
                    session=session,
                    role="assistant",
                    content=reply,
                    metadata={
                        "agent": "master_agent",
                        "capability_pack": MASTER_AGENT_CAPABILITY_PACK["version"],
                        "operation_id": operation.operation_id,
                        "execution": "forbidden",
                    },
                )
                return reply
            approval = ApprovalRequest.objects.create(
                action_type="chat:" + operation.action,
                target_type="ChatOperation",
                target_id=operation.operation_id,
                reason=approval_reason(operation),
                risk=operation.risk,
                status="approved" if direct_owner else "pending",
                decision_note="direct_owner_chat_execution" if direct_owner else "",
                requested_by=session.user,
            )
            if direct_owner:
                from .operation_executor import execute_approved_chat_operation
                import json
                try:
                    result = execute_approved_chat_operation(approval)
                    reply = (
                        "اجرا انجام شد. "
                        f"عملیات: {operation.action} | "
                        + json.dumps(result.get("result", result), ensure_ascii=False, default=str)[:3500]
                    )
                    execution = "direct_owner_chat_executed"
                except Exception as exc:
                    # The executor owns terminal states. Never reset an already
                    # claimed action to "approved" or hide an ambiguous outcome.
                    AuditLog.objects.create(
                        actor_type="owner_chat",
                        actor_id=str(session.user.pk),
                        action="chat_operation_failed",
                        target_type="ApprovalRequest",
                        target_id=str(approval.pk),
                        after_state={"operation": operation.action, "error": type(exc).__name__},
                        trace_id="chat-operation-failed-" + operation.operation_id,
                    )
                    reply = "اجرای مستقیم ناموفق بود و هیچ موفقیتی گزارش نشده است: " + type(exc).__name__
                    execution = "direct_owner_chat_failed"
            else:
                reply = (
                    "درخواست عملیاتی ثبت شد و هنوز اجرا نشده است. "
                    f"شماره تأیید: {approval.pk} | عملیات: {operation.action} | "
                    "این درخواست فقط پس از تأیید مالک اجرا می‌شود."
                )
                execution = "approval_required"
            ChatMessage.objects.create(
                session=session,
                role="assistant",
                content=reply,
                metadata={
                    "agent": "master_agent",
                    "capability_pack": MASTER_AGENT_CAPABILITY_PACK["version"],
                    "operation_id": operation.operation_id,
                    "approval_id": approval.pk,
                    "execution": execution,
                },
            )
            return reply

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            reply = (
                "پیام دریافت شد. اتصال مدل هوش مصنوعی هنوز در محیط سرور "
                "پیکربندی نشده است؛ بنابراین هیچ اقدامی اجرا نشد."
            )
        else:
            client = OpenAI(api_key=api_key)
            history = list(session.messages.order_by("-created_at")[:20])
            messages = [
                {"role": "system", "content": master_system_prompt()},
                *[
                    {"role": item.role, "content": item.content}
                    for item in reversed(history)
                    if item.role in {"user", "assistant"}
                ],
            ]
            response = client.chat.completions.create(
                model=os.getenv("OPENAI_CHAT_MODEL", "gpt-5.6"),
                messages=messages,
            )
            reply = response.choices[0].message.content or ""

        ChatMessage.objects.create(
            session=session,
            role="assistant",
            content=reply,
            metadata={"agent": "master_agent", "capability_pack": MASTER_AGENT_CAPABILITY_PACK["version"]},
        )
        return reply
