import os

from openai import OpenAI

from .models import ChatMessage
from .master_agent_capability_pack import capability_pack_prompt


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

        # Ordinary chat can now produce a bounded operation request. The chat
        # never executes it directly: it creates an owner approval record.
        from .operation_planner import approval_reason, plan_chat_operation
        from .models import ApprovalRequest

        operation = plan_chat_operation(text)
        if operation is not None:
            approval = ApprovalRequest.objects.create(
                action_type="chat:" + operation.action,
                target_type="ChatOperation",
                target_id=operation.operation_id,
                reason=approval_reason(operation),
                risk=operation.risk,
                status="pending",
                requested_by=session.user,
            )
            reply = (
                "درخواست عملیاتی ثبت شد و هنوز اجرا نشده است. "
                f"شماره تأیید: {approval.pk} | عملیات: {operation.action} | "
                "پس از تأیید مالک، worker سایت آن را فقط در محدوده مجاز اجرا و نتیجه را ثبت می‌کند."
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
            metadata={"agent": "master_agent", "capability_pack": "1.0.0"},
        )
        return reply
