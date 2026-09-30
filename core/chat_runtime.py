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
