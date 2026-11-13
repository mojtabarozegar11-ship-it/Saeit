"""Authenticated Django conversation through the existing canonical bot.

No second agent, scheduler, queue, website or external action is created.
Conversation history stays in the existing Django ChatSession tables.
"""
from __future__ import annotations

import os

from ava_core import MojtabaBot
from .bot_identity import BOT_ID
from .models import ChatSession


def respond_with_mojtaba_runtime(session, text: str, *, system_prompt: str) -> str:
    if (not session.user.is_authenticated or not session.user.is_active
            or session.status != "active" or not isinstance(text, str)
            or not 0 < len(text.strip()) <= 10000):
        raise PermissionError("CANONICAL_CHAT_SESSION_NOT_AUTHORIZED")
    if not isinstance(system_prompt, str) or not system_prompt.strip():
        raise ValueError("CANONICAL_CHAT_SYSTEM_PROMPT_REQUIRED")
    if not ChatSession.objects.filter(
            pk=session.pk, user_id=session.user_id, status="active").exists():
        raise PermissionError("CANONICAL_CHAT_SESSION_OWNER_MISMATCH")
    if not session.user.is_superuser:
        # Non-owner users cannot trigger billable provider calls merely by
        # holding an ordinary chat session, even if the host enables a model.
        return ("گفتگو ثبت شد؛ اجرای مدل بیرونی برای این حساب "
                "نیازمند مجوز جداگانه مالک است.")

    # A configured API key does not itself authorize a billable provider call.
    key = os.getenv("OPENAI_API_KEY")
    if not key or os.getenv("MOJTABA_CHAT_EXTERNAL_MODEL_ENABLED") != "1":
        return ("پیام دریافت شد. اجرای مدل بیرونی در این محیط مجاز یا "
                "پیکربندی نشده است؛ هیچ اقدام خارجی انجام نشد.")

    # This turn has already been persisted by MasterAgentChat. Exclude the
    # current message from history to avoid charging for a duplicate turn.
    history = list(session.messages.order_by("-created_at", "-pk")[:21])
    current_id = next(
        (item.pk for item in history
         if item.role == "user" and item.content == text), None
    )
    previous = [
        item for item in reversed(history)
        if item.pk != current_id and item.role in {"user", "assistant"}
    ][-12:]

    def brain(messages):
        from openai import OpenAI
        # One provider request and no tool-calling API. Even a model-produced
        # imperative cannot execute an action or approve an operation.
        trusted = [dict(item) for item in messages[:-1]]
        prior = [
            {"role": item.role, "content": item.content[:10000]}
            for item in previous
        ]
        result = OpenAI(api_key=key).chat.completions.create(
            model=os.getenv("OPENAI_CHAT_MODEL", "gpt-5.6"),
            messages=[
                *trusted,
                {"role": "system", "content": system_prompt[:6000]},
                *prior,
                dict(messages[-1]),
            ],
            max_completion_tokens=1200,
        )
        return result.choices[0].message.content or ""

    bot = MojtabaBot(
        owner_id=f"django-user:{session.user_id}",
        brain=brain,
        propose_goals=lambda _history: (),
    )
    if bot.bot_name != BOT_ID:
        raise RuntimeError("CANONICAL_BOT_IDENTITY_MISMATCH")
    return bot.converse(text).reply.text
