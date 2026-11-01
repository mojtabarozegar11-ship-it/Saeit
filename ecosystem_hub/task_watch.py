"""Private, deterministic unit-level smart calendar triage for Zomorod.

Reads existing WorkTask records. Does not change task status, message anyone,
make financial commitments, or trigger real-world factory operations.
"""
from datetime import timedelta

from django.core.exceptions import PermissionDenied
from django.db.models import Case, Count, IntegerField, Q, Value, When
from django.utils import timezone

from enterprise_portal.models import WorkTask
from .access import require_unit


def watch_for_unit(unit, *, actor, today=None, limit=8):
    """Return disjoint due-date buckets and an actionable, bounded task queue.

    Enforce view_worktask, unit membership and office task row visibility here.
    The urgent bucket overlaps due buckets by design.
    """
    require_unit(actor, unit)
    if not (actor.is_superuser or actor.has_perm("enterprise_portal.view_worktask")):
        raise PermissionDenied("مجوز مشاهده وظایف این واحد موجود نیست.")
    today = today or timezone.localdate()
    week_end = today + timedelta(days=7)
    active = WorkTask.objects.filter(unit=unit).exclude(status="done")
    # Match enterprise_portal.views.tasks: readers without change_worktask
    # may inspect only their assigned or personally issued tasks.
    if not (actor.is_superuser or actor.has_perm("enterprise_portal.change_worktask")):
        active = active.filter(Q(assigned_to=actor) | Q(created_by=actor))
    counts = active.aggregate(
        open=Count("pk"),
        overdue=Count("pk", filter=Q(due_on__lt=today)),
        due_today=Count("pk", filter=Q(due_on=today)),
        due_soon=Count("pk", filter=Q(due_on__gt=today, due_on__lte=week_end)),
        urgent=Count("pk", filter=Q(priority="urgent")),
        no_due=Count("pk", filter=Q(due_on__isnull=True)),
    )
    tasks = list(
        active.filter(Q(due_on__lte=week_end) | Q(priority="urgent"))
        .annotate(watch_order=Case(
            When(due_on__lt=today, then=Value(0)),
            When(priority="urgent", then=Value(1)),
            When(due_on=today, then=Value(2)),
            default=Value(3),
            output_field=IntegerField(),
        ))
        .select_related("assigned_to")
        .order_by("watch_order", "due_on", "pk")[:max(1, min(limit, 12))]
    )
    return {"counts": counts, "tasks": tasks, "as_of": today}
