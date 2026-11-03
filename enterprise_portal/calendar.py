"""Private, permission-scoped Zomorod calendar: meetings and assigned work.

All reads are restricted to the signed-in company account. A calendar GET never
sends messages, incurs a charge, mutates financial data, or runs agents.
"""
import calendar as cal
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone as utc_timezone
from urllib.parse import urlencode

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_http_methods

from .forms import MeetingForm
from .models import Meeting
from .views import _visible_tasks, no_cache, office_access, page


def _meeting_access(user):
    records = Meeting.objects.all()
    if not user.is_superuser:
        records = records.filter(Q(organizer=user) | Q(attendees=user)).distinct()
    return records


def _can_view(user, model):
    return user.is_superuser or user.has_perm("enterprise_portal.view_" + model)


def _month(request):
    raw = (request.GET.get("month") or "").strip()
    if not raw:
        return timezone.localdate().replace(day=1)
    try:
        value = date.fromisoformat(raw + "-01")
    except (ValueError, TypeError):
        return None
    return value if value.strftime("%Y-%m") == raw else None


def _next_month(first):
    return (first.replace(day=28) + timedelta(days=4)).replace(day=1)


@never_cache
@office_access
@require_GET
def calendar_view(request):
    user = request.user
    show_meetings = _can_view(user, "meeting")
    show_tasks = _can_view(user, "worktask")
    if not show_meetings and not show_tasks:
        raise PermissionDenied("مجوز مشاهده تقویم سازمانی موجود نیست.")

    first = _month(request)
    if first is None or first.year < 2000 or first.year > 2100:
        return no_cache(HttpResponse("ماه نامعتبر است.", status=400))
    next_first = _next_month(first)
    previous = first - timedelta(days=1)
    days = cal.Calendar(firstweekday=5).monthdatescalendar(first.year, first.month)
    first_day, last_day = days[0][0], days[-1][-1]
    now = timezone.localdate()
    event_map = defaultdict(list)

    if show_meetings:
        meetings = _meeting_access(user).filter(
            starts_at__date__gte=first_day,
            starts_at__date__lte=last_day,
        ).order_by("starts_at", "pk")[:500]
        for item in meetings:
            day = timezone.localtime(item.starts_at).date()
            event_map[day].append({
                "type": "meeting", "title": item.title, "time": timezone.localtime(item.starts_at),
                "url": reverse("enterprise_portal:meeting_ics", args=[item.pk]),
                "priority": "", "overdue": False,
            })

    if show_tasks:
        tasks = _visible_tasks(user).filter(
            due_on__gte=first_day, due_on__lte=last_day,
        ).select_related("assigned_to").order_by("due_on", "-priority", "pk")[:500]
        for item in tasks:
            event_map[item.due_on].append({
                "type": "task", "title": item.title, "time": None,
                "url": reverse("enterprise_portal:task_detail", args=[item.pk]),
                "priority": item.priority,
                "overdue": item.status != "done" and item.due_on < now,
            })

    weeks = []
    for week in days:
        weeks.append([
            {
                "date": day, "in_month": day.month == first.month,
                "today": day == now, "events": event_map[day][:12],
                "overflow": max(0, len(event_map[day]) - 12),
            }
            for day in week
        ])
    return page(request, "calendar", {
        "section": "calendar",
        "current_month": first,
        "previous_month": previous.strftime("%Y-%m"),
        "next_month": next_first.strftime("%Y-%m"),
        "weeks": weeks,
        "can_add_meeting": user.is_superuser or user.has_perm("enterprise_portal.add_meeting"),
        "show_meetings": show_meetings, "show_tasks": show_tasks,
    })


@never_cache
@office_access
@csrf_protect
@require_http_methods(["GET", "POST"])
def new_meeting(request):
    user = request.user
    if not (user.is_superuser or user.has_perm("enterprise_portal.add_meeting")):
        raise PermissionDenied("مجوز ثبت جلسه موجود نیست.")
    form = MeetingForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        item = form.save(commit=False)
        item.organizer = user
        with transaction.atomic():
            # Keep the organizer's conflicting meetings out of one schedule.
            get_user_model().objects.select_for_update().get(pk=user.pk)
            conflict = Meeting.objects.filter(
                organizer=user,
                starts_at__lt=item.ends_at,
                ends_at__gt=item.starts_at,
            ).exists()
            if conflict:
                form.add_error(None, "این بازه با جلسه دیگری که برگزارکننده آن هستید تداخل دارد.")
            else:
                item.full_clean()
                item.save()
                return redirect(reverse("enterprise_portal:calendar") + "?" + urlencode({
                    "month": timezone.localtime(item.starts_at).strftime("%Y-%m"),
                }))
    return page(request, "form", {
        "section": "calendar", "heading": "ثبت جلسه در تقویم هوشمند",
        "form": form, "submit_label": "ثبت جلسه",
        "back_url": reverse("enterprise_portal:calendar"),
    })


def _ics_escape(value):
    return (str(value).replace("\\", "\\\\").replace("\r\n", "\n")
            .replace("\r", "\n").replace("\n", "\\n")
            .replace(",", "\\,").replace(";", "\\;"))


@never_cache
@office_access
@require_GET
def meeting_ics(request, pk):
    if not _can_view(request.user, "meeting"):
        raise PermissionDenied("مجوز مشاهده جلسه موجود نیست.")
    meeting = get_object_or_404(_meeting_access(request.user), pk=pk)
    def stamp(value):
        return value.astimezone(utc_timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Zomorod Melal//Private Office//FA",
        "CALSCALE:GREGORIAN", "BEGIN:VEVENT",
        "UID:zm-private-meeting-" + str(meeting.pk) + "@zomorodmelal.ir",
        "DTSTAMP:" + stamp(timezone.now()),
        "DTSTART:" + stamp(meeting.starts_at),
        "DTEND:" + stamp(meeting.ends_at),
        "SUMMARY:" + _ics_escape(meeting.title),
        "DESCRIPTION:" + _ics_escape(meeting.agenda),
        "LOCATION:" + _ics_escape(meeting.location),
        "END:VEVENT", "END:VCALENDAR", "",
    ]
    response = HttpResponse("\r\n".join(lines), content_type="text/calendar; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="zm-meeting-' + str(meeting.pk) + '.ics"'
    response["X-Content-Type-Options"] = "nosniff"
    return no_cache(response)
