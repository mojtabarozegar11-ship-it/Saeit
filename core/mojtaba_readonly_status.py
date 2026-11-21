"""Bounded, no-model operational census for the authenticated owner.

Only exact user commands trigger this handler. Counts are SELECT-only snapshots;
they are not evidence of process topology, real customer conversion or revenue.
This module never schedules work, grants privileges, calls an LLM or changes data.
"""
import os

from django.db import connections, DatabaseError

from core.chat_operation_security import is_authorized_chat_operator
from core.models import Agent, AgentTask, ApprovalRequest, ChatSession
from core.unified_bot_identity import BOT_CODE


STATUS_COMMANDS = frozenset({
    "bot status", "mojtaba status", "mojtaba.bot.ai status",
    "وضعیت ربات", "گزارش وضعیت ربات",
})
TERMINAL_STATES = ("completed", "failed", "cancelled")


def is_status_command(text):
    """Exact phrase only; avoid interpreting an ordinary question as authority."""
    if not isinstance(text, str):
        return False
    return " ".join(text.strip().casefold().rstrip(" ؟?!.").split()) in STATUS_COMMANDS


def _isolated_prop_counts():
    """Read isolated MOJ PROP figures or report unknown; never fake zeros."""
    from config.mojprop_db_router import MOJPROP_DB_ALIAS
    from prop_firm.models import (
        PropSimulationAccount, PropSimulationInvoiceOwner, PropSimulationPayment,
    )
    if MOJPROP_DB_ALIAS not in connections:
        return None
    try:
        return {
            "invoices": PropSimulationInvoiceOwner.objects.using(MOJPROP_DB_ALIAS).count(),
            "payments": PropSimulationPayment.objects.using(MOJPROP_DB_ALIAS).count(),
            "accounts": PropSimulationAccount.objects.using(MOJPROP_DB_ALIAS).count(),
        }
    except (DatabaseError, OSError, ValueError):
        # An isolated DB failure is not a valid zero-sales measurement.
        return None


def owner_runtime_snapshot(user):
    """Return a strictly owner-authorized summary of existing Django records."""
    if not is_authorized_chat_operator(user):
        raise PermissionError("Active superuser required for operational census")

    # Every query is a SELECT; even an unconfigured or unavailable AI key is
    # only a configuration-presence signal, not inference readiness.
    return {
        "registered_agents": Agent.objects.count(),
        "active_agents": Agent.objects.filter(active=True).count(),
        "canonical_agents": Agent.objects.filter(code=BOT_CODE, active=True).count(),
        "nonterminal_tasks": AgentTask.objects.exclude(
            status__in=TERMINAL_STATES,
        ).count(),
        "queued_tasks": AgentTask.objects.filter(status="queued").count(),
        "blocked_tasks": AgentTask.objects.filter(status="blocked").count(),
        "chat_sessions": ChatSession.objects.count(),
        "pending_chat_approvals": ApprovalRequest.objects.filter(
            target_type="ChatOperation", status="pending",
        ).count(),
        "provider_key_present": bool(os.environ.get("OPENAI_API_KEY")),
        "prop": _isolated_prop_counts(),
    }


def render_owner_status(snapshot):
    """Operational report; no inferred income, bot-worker or model claims."""
    prop = snapshot["prop"]
    prop_text = (
        "آمار بانک مستقل مج‌پراپ: نامشخص (در دسترس نیست)"
        if prop is None else
        "بانک مج‌پراپ: "
        f"{prop['invoices']} فاکتور، "
        f"{prop['payments']} پرداخت ثبت‌شده، "
        f"{prop['accounts']} حساب شبیه‌سازی"
    )
    return (
        "گزارش فقط‌خواندنی ربات مرکزی — mojtaba.bot.ai\n"
        f"هویت‌های ثبت‌شده: {snapshot['registered_agents']} "
        f"(فعال: {snapshot['active_agents']})؛ "
        f"هویت مرکزی فعال: {snapshot['canonical_agents']}\n"
        f"وظایف غیرنهایی: {snapshot['nonterminal_tasks']} "
        f"(در صف: {snapshot['queued_tasks']}؛ "
        f"مسدود: {snapshot['blocked_tasks']})\n"
        f"نشست‌های گفت‌وگو: {snapshot['chat_sessions']}؛ "
        f"تأییدهای معوق فرمان چت: {snapshot['pending_chat_approvals']}\n"
        + prop_text + "\n"
        + ("کلید مدل در محیط این پردازش موجود است؛ پاسخ‌گویی مدل اثبات نشده."
           if snapshot["provider_key_present"] else
           "کلید مدل در محیط این پردازش ثبت نشده است.") + "\n"
        "این اعداد صرفاً داده‌های ثبت‌شده‌اند؛ فعالیت یک هسته واحد، "
        "وصول درآمد، تحویل خدمت یا اجرای فرمان را اثبات نمی‌کنند. "
        "هیچ عملیات اجرایی انجام نشد."
    )
