"""Explicit human task workflow for Zomorod office.

This module authorizes status changes; it does not run agents, pay, publish,
send messages, alter inventory, or operate factory hardware.
"""

TRANSITIONS = {
    "start": ("todo", "doing", "شروع کار"),
    "submit": ("doing", "review", "ارسال نتیجه برای بازبینی"),
    "approve": ("review", "done", "تأیید تکمیل"),
    "rework": ("review", "doing", "بازگشت برای اصلاح"),
}


def available_actions(actor, task):
    """Only actors allowed to change this task's current state receive actions.

    The calling view must also enforce office access, view_worktask, and
    per-unit/per-row visibility before using the result.
    """
    is_assignee = task.assigned_to_id == actor.pk
    can_manage = actor.is_superuser or actor.has_perm("enterprise_portal.change_worktask")
    can_review = can_manage and (actor.is_superuser or not is_assignee)
    offered = []
    for code, (before, after, title) in TRANSITIONS.items():
        if task.status != before:
            continue
        if code == "start" and not (is_assignee or can_manage):
            continue
        if code == "submit" and not is_assignee:
            continue
        if code in ("approve", "rework") and not can_review:
            continue
        offered.append({"code": code, "target": after, "label": title})
    return offered
