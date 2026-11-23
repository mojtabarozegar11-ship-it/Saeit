from .models import ChatMessage
from .master_agent_capability_pack import capability_pack_prompt
from .chat_operation_security import is_authorized_chat_operator


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

        # This is a bounded, local database census, not a language model.
        # No task execution, external request or owner-command auto approval.
        from django.db import DatabaseError
        from .mojtaba_readonly_status import (
            is_status_command, owner_runtime_snapshot, render_owner_status,
        )
        if is_status_command(text):
            if not is_authorized_chat_operator(session.user):
                reply = "گزارش مدیریتی از این حساب مجاز نیست."
                execution = "forbidden"
            else:
                try:
                    reply = render_owner_status(owner_runtime_snapshot(session.user))
                    execution = "read_only_status"
                except DatabaseError:
                    reply = "گزارش وضعیت قابل دریافت نیست؛ صحت بانک اطلاعاتی باید بررسی شود."
                    execution = "read_only_unavailable"
            ChatMessage.objects.create(
                session=session,
                role="assistant",
                content=reply,
                metadata={
                    "agent": "master_agent",
                    "capability_pack": "1.0.0",
                    "execution": execution,
                    "llm_called": False,
                },
            )
            return reply


        # Explicit operational language creates only a pending operation.
        # Merely chatting as a superuser is NOT an independent authorization to
        # perform deployment, external writes, or other privileged side effects.
        # ApprovalService decides separately; the approved-operation executor
        # retains its idempotent, auditable one-shot claim.
        from .operation_planner import approval_reason, plan_chat_operation
        from .models import ApprovalRequest

        operation = plan_chat_operation(text)
        if operation is not None:
            direct_owner = is_authorized_chat_operator(session.user)
            if not direct_owner:
                reply = "اجرای دستور مدیریتی از این حساب مجاز نیست؛ فقط مدیر ارشد فعال می‌تواند دستور عملیاتی صادر کند."
                ChatMessage.objects.create(
                    session=session,
                    role="assistant",
                    content=reply,
                    metadata={
                        "agent": "master_agent",
                        "capability_pack": "1.0.0",
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
                status="pending",
                decision_note="separate_owner_decision_required",
                requested_by=session.user,
            )
            reply = (
                "درخواست مدیریتی ثبت شد، اما هنوز هیچ عملیاتی اجرا نشده است. "
                f"شناسه تأیید: {approval.pk} | عملیات: {operation.action}. "
                "ابتدا تصمیم مستقل مالک در سامانه تأییدات لازم است. "
                "تا زمان تأیید و اجرای کنترل‌شده، استقرار یا تغییر داده انجام نمی‌شود."
            )
            ChatMessage.objects.create(
                session=session,
                role="assistant",
                content=reply,
                metadata={
                    "agent": "master_agent",
                    "capability_pack": "1.0.0",
                    "operation_id": operation.operation_id,
                    "approval_id": approval.pk,
                    "execution": "approval_required",
                },
            )
            return reply

        # A configured API key is NOT case-specific consent for a billable
        # model call. Keep public customer chat in a deterministic, API-free
        # intake mode until a scoped one-time grant can be verified here.
        # Never send customer-supplied text to an external model by default.
        reply = (
            "پیام دریافت و ثبت شد. پردازش هوش مصنوعی پولی برای این درخواست "
            "مجوز اختصاصی ندارد و فراخوانی نشده است. "
            "برای خدمات یا پیگیری، از مسیر رسمی درخواست و پشتیبانی استفاده کنید."
        )

        ChatMessage.objects.create(
            session=session,
            role="assistant",
            content=reply,
            metadata={
                "agent": "master_agent",
                "capability_pack": "1.0.0",
                "execution": "local_no_external_ai_api",
                "llm_called": False,
            },
        )
        return reply
