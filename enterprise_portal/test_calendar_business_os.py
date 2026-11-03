"""Regression for Zomorod calendar, real meeting lifecycle and data isolation."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from ecosystem_hub.models import UnitMembership
from .models import BusinessUnit, Meeting, WorkTask


@override_settings(DEBUG=True, COMPANY_OFFICE_REQUIRE_MFA=False)
class CompanyCalendarTests(TestCase):
    def setUp(self):
        users = get_user_model()
        self.manager = users.objects.create_user(
            username="calendar_manager", password="OnlyForTest!12345",
            is_staff=True, is_active=True,
        )
        self.other = users.objects.create_user(
            username="other_manager", password="OnlyForTest!12345",
            is_staff=True, is_active=True,
        )
        for person in (self.manager, self.other):
            permissions = Permission.objects.filter(
                content_type__app_label="enterprise_portal",
                codename__in=("view_businessunit", "view_meeting", "add_meeting",
                             "view_worktask"),
            )
            person.user_permissions.add(*permissions)
        self.unit = BusinessUnit.objects.create(code="test-zm-calendar", name="دفتر")
        self.other_unit = BusinessUnit.objects.create(code="test-zm-other", name="واحد محرمانه")
        UnitMembership.objects.create(user=self.manager, unit=self.unit, role="manager")
        UnitMembership.objects.create(user=self.other, unit=self.other_unit, role="manager")
        self.start = timezone.now().replace(second=0, microsecond=0) + timedelta(days=1)
        self.end = self.start + timedelta(hours=1)
        self.own_meeting = Meeting.objects.create(
            title="جلسه داخلی مدیر", agenda="گزارش پروژه", starts_at=self.start,
            ends_at=self.end, organizer=self.manager,
        )
        self.private_meeting = Meeting.objects.create(
            title="جلسه محرمانه واحد دیگر", agenda="اطلاعات محرمانه",
            starts_at=self.start, ends_at=self.end, organizer=self.other,
        )
        self.own_task = WorkTask.objects.create(
            title="کار مربوط به مدیر", unit=self.unit, assigned_to=self.manager,
            created_by=self.manager, due_on=timezone.localdate(self.start),
        )
        WorkTask.objects.create(
            title="کار محرمانه واحد دیگر", unit=self.other_unit, assigned_to=self.other,
            created_by=self.other, due_on=timezone.localdate(self.start),
        )
        self.client.force_login(self.manager)

    def test_calendar_renders_own_meeting_and_task_not_other_unit(self):
        url = reverse("enterprise_portal:calendar")
        response = self.client.get(url, {"month": timezone.localdate(self.start).strftime("%Y-%m")}, secure=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "جلسه داخلی مدیر")
        self.assertContains(response, "کار مربوط به مدیر")
        self.assertNotContains(response, "جلسه محرمانه واحد دیگر")
        self.assertNotContains(response, "کار محرمانه واحد دیگر")
        self.assertIn("no-store", response["Cache-Control"])
        self.assertContains(response, "تقویم هوشمند")

    def test_invalid_month_rejected_and_no_https_bypass(self):
        url = reverse("enterprise_portal:calendar")
        self.assertEqual(self.client.get(url, {"month": "2030-99"}, secure=True).status_code, 400)
        self.assertEqual(self.client.get(url).status_code, 200)  # DEBUG=True permits local test HTTP.
        with override_settings(DEBUG=False):
            self.assertEqual(self.client.get(url).status_code, 403)

    def test_unauthorized_and_anonymous_calendar_access(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("enterprise_portal:calendar"), secure=True).status_code, 302)
        self.client.force_login(self.manager)
        self.manager.user_permissions.clear()
        self.assertEqual(self.client.get(reverse("enterprise_portal:calendar"), secure=True).status_code, 403)

    def test_new_meeting_and_overlap_rejection(self):
        url = reverse("enterprise_portal:new_meeting")
        next_start = self.start + timedelta(days=3)
        data = {
            "title": "جلسه جدید مدیر",
            "agenda": "صورت جلسه",
            "starts_at": timezone.localtime(next_start).strftime("%Y-%m-%dT%H:%M"),
            "ends_at": timezone.localtime(next_start + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M"),
            "location": "دفتر مرکزی",
        }
        response = self.client.post(url, data, secure=True)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Meeting.objects.filter(title=data["title"], organizer=self.manager).count(), 1)
        overlap = dict(data, title="هم‌پوشانی ممنوع")
        response = self.client.post(url, overlap, secure=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "تداخل دارد")
        self.assertFalse(Meeting.objects.filter(title=overlap["title"]).exists())

    def test_meeting_ics_does_not_leak_other_meetings_or_inject_lines(self):
        self.own_meeting.title = "عنوان\nX-UNSAFE:injected"
        self.own_meeting.save(update_fields=["title"])
        own = self.client.get(reverse("enterprise_portal:meeting_ics", args=[self.own_meeting.pk]), secure=True)
        self.assertEqual(own.status_code, 200)
        self.assertEqual(own["Content-Type"], "text/calendar; charset=utf-8")
        self.assertIn(b"SUMMARY:", own.content)
        self.assertNotIn(b"\r\nX-UNSAFE:injected", own.content)
        self.assertIn(b"\\nX-UNSAFE:injected", own.content)
        forbidden = self.client.get(reverse("enterprise_portal:meeting_ics", args=[self.private_meeting.pk]), secure=True)
        self.assertEqual(forbidden.status_code, 404)

    def test_csrf_enforced_on_creating_meeting(self):
        secure_client = Client(enforce_csrf_checks=True)
        secure_client.force_login(self.manager)
        result = secure_client.post(reverse("enterprise_portal:new_meeting"), {
            "title": "بدون توکن", "agenda": "متن",
            "starts_at": "2026-11-14T10:00", "ends_at": "2026-11-14T11:00",
        }, secure=True)
        self.assertEqual(result.status_code, 403)
        self.assertFalse(Meeting.objects.filter(title="بدون توکن").exists())
