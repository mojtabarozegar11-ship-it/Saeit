from .models import ChatMessage
from .master_agent_capability_pack import MASTER_AGENT_CAPABILITY_PACK, capability_pack_prompt
from .chat_operation_security import is_authorized_chat_operator
from .cyber_defense import make_security_event, seal_evidence, triage_security_events
from .bot_identity import BOT_ID


SYSTEM_PROMPT = """
You are Mojtaba.bot.ai, the single unified Master Agent assistant for Saeit.
Other agents and workers are internal specialist components, not independent bots.
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

        if not getattr(session.user, "is_authenticated", False) or not session.user.is_active:
            raise PermissionError("Authenticated active chat session owner required")
        if session.status != "active":
            raise PermissionError("Inactive chat session")
        if len(text) > 10000:
            raise ValueError("Chat message exceeds 10000 characters")
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
                        "bot_id": BOT_ID,
                        "capability_pack": MASTER_AGENT_CAPABILITY_PACK["version"],
                        "operation_id": operation.operation_id,
                        "execution": "forbidden",
                    },
                )
                return reply
            # An authenticated superuser may REQUEST a binding operation,
            # but never implicitly grant its own production/write approval
            # simply by sending a chat message. Existing approval lifecycle
            # and execution receipts remain the only authority.
            approval = ApprovalRequest.objects.create(
                action_type="chat:" + operation.action,
                target_type="ChatOperation",
                target_id=operation.operation_id,
                reason=approval_reason(operation, session_id=session.pk),
                risk=operation.risk,
                status="pending",
                requested_by=session.user,
            )
            reply = (
                "دستور ثبت شد، اما اجرا نشده است. "
                f"شماره درخواست: {approval.pk} | عملیات: {operation.action} | "
                "ابتدا تأیید موردی مالک و سپس فرمان اجرای جداگانه لازم است."
            )
            execution = "pending_explicit_owner_approval"
            ChatMessage.objects.create(
                session=session,
                role="assistant",
                content=reply,
                metadata={
                    "agent": "master_agent",
                    "bot_id": BOT_ID,
                    "capability_pack": MASTER_AGENT_CAPABILITY_PACK["version"],
                    "operation_id": operation.operation_id,
                    "approval_id": approval.pk,
                    "execution": execution,
                },
            )
            return reply

        # The only canonical in-process conversation engine. Operational
        # commands are already routed to the durable owner approval flow.
        from .canonical_chat_bridge import respond_with_mojtaba_runtime
        reply = respond_with_mojtaba_runtime(
            session, text, system_prompt=master_system_prompt(),
        )

        ChatMessage.objects.create(
            session=session,
            role="assistant",
            content=reply,
            metadata={"agent": "master_agent", "bot_id": BOT_ID, "capability_pack": MASTER_AGENT_CAPABILITY_PACK["version"]},
        )
        return reply
