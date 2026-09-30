import os

from openai import OpenAI

from .models import ChatMessage
from .master_agent_capability_pack import capability_pack_prompt, MASTER_AGENT_CAPABILITY_PACK
from .commander_orchestrator import CommanderOrchestrator


SYSTEM_PROMPT = """
You are Commander Gen-15 for Saeit: an intelligent, result-oriented digital executive.
Reason, plan, delegate and use only registered/authorized execution capabilities.
Never claim that an action was executed when it was only discussed.
Never invent tool access. Sensitive actions such as deployment, payments, credentials,
external writes, deletion, legal commitments or irreversible production changes require
an explicit Owner Approval recorded by the backend. Keep responses operational.
"""


def master_system_prompt(available_capabilities=None):
    available = ", ".join(available_capabilities or []) or "none currently registered"
    return (
        SYSTEM_PROMPT.strip()
        + "\n\n"
        + capability_pack_prompt()
        + f"\nRuntime execution capabilities currently registered: {available}."
    )


class MasterAgentChat:
    def __init__(self, orchestrator=None):
        self.orchestrator = orchestrator or CommanderOrchestrator()

    def respond(self, session, user_text):
        text = str(user_text or "").strip()
        if not text:
            raise ValueError("Message cannot be empty")

        ChatMessage.objects.create(session=session, role="user", content=text)
        available = self.orchestrator.available_capabilities()
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            reply = (
                "پیام دریافت شد. اتصال مدل هوش مصنوعی در محیط سرور پیکربندی نشده؛ "
                "بنابراین هیچ اقدام اجرایی انجام نشد."
            )
        else:
            client = OpenAI(api_key=api_key)
            history = list(session.messages.order_by("-created_at")[:20])
            messages = [
                {"role": "system", "content": master_system_prompt(available)},
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
            metadata={
                "agent": "commander_gen15",
                "generation": MASTER_AGENT_CAPABILITY_PACK["identity"]["generation"],
                "capability_pack": MASTER_AGENT_CAPABILITY_PACK["version"],
                "execution_capabilities": available,
            },
        )
        return reply

    def execute(self, *, capability_code, input_data, project=None,
                action_type="execute", owner=None):
        """Execute a concrete registered capability through governance controls."""
        return self.orchestrator.execute_capability(
            capability_code=capability_code,
            input_data=input_data,
            project=project,
            action_type=action_type,
            owner=owner,
        )
