"""Regression checks for legacy office records without business-unit foreign keys."""
from datetime import timedelta

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase, RequestFactory, override_settings
from django.utils import timezone

from enterprise_portal.forms import LetterForm, TaskForm
from enterprise_portal.models import (
    AuditEvent, BusinessUnit, Meeting, OfficeLetter, WorkTask,
)
from .models import UnitMembership


TEST_STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


@override_settings(STORAGES=TEST_STORAGES, DEBUG=False, ALLOWED_HOSTS=["testserver"])
class OfficeTenantPrivacyTests(TestCase):
    def setUp(self):
        users = get_user_model()
        self.farm = BusinessUnit.objects.create(code="farm", name="کشاورزی")
        self.factory = BusinessUnit.objects.create(code="factory", name="صنعت")
        self.owner = users.objects.create_superuser(
            username="owner-tenant-test", email="owner@example.org", password="unrelated",
        )
        self.alice = users.objects.create_user(
            username="alice-tenant", password="unrelated", is_staff=True,
        )
        self.bob = users.objects.create_user(
            username="bob-tenant", password="unrelated", is_staff=True,
        )
        UnitMembership.objects.create(user=self.alice, unit=self.farm, role="analyst")
        UnitMembership.objects.create(user=self.bob, unit=self.factory, role="operations")
        self.grant(self.alice, "view_businessunit")

    def grant(self, user, *codes):
        user.user_permissions.add(*Permission.objects.filter(
            content_type__app_label="enterprise_portal", codename__in=codes,
        ))

    def request(self, user, path):
        r = RequestFactory().get(path)
        r.user = user
        return r

    def test_unrelated_ordinary_and_confidential_letters_are_not_exposed(self):
        self.grant(self.alice, "view_officeletter", "view_confidential_letters")
        hidden = OfficeLetter.objects.create(
            number="OFF-H1", subject="متن شرکت دیگر", direction="internal",
            classification="normal", body="پنهان", created_by=self.owner,
        )
        visible = OfficeLetter.objects.create(
            number="OFF-V1", subject="نامه ارجاع شده", direction="internal",
            classification="confidential", body="مرئی برای گیرنده",
            created_by=self.owner, assigned_to=self.alice,
        )
        self.client.force_login(self.alice)
        response = self.client.get("/company/office/letters/", secure=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, visible.subject)
        self.assertNotContains(response, hidden.subject)
        self.assertNotContains(response, hidden.body)
        panel = admin.site._registry[OfficeLetter]
        req = self.request(self.alice, "/admin/enterprise_portal/officeletter/")
        self.assertEqual(list(panel.get_queryset(req)), [visible])
        self.assertFalse(panel.has_view_permission(req, hidden))
        self.assertFalse(panel.has_change_permission(req, visible))
        self.assertEqual(panel.get_queryset(self.request(self.owner, "/admin/")).count(), 2)

    def test_unscoped_admin_letter_create_does_not_crash_or_need_unit(self):
        panel = admin.site._registry[OfficeLetter]
        obj = OfficeLetter(
            number="ADMIN-1", subject="نامه دفتر", direction="internal",
            body="متن", classification="normal",
        )
        panel.save_model(self.request(self.owner, "/admin/"), obj, None, False)
        self.assertEqual(OfficeLetter.objects.get(pk=obj.pk).created_by, self.owner)

    def test_letter_assignees_must_be_colleagues_not_other_tenants(self):
        fields = {
            "number": "L-1", "subject": "نامه داخلی", "direction": "internal",
            "body": "متن داخلی", "classification": "normal", "sent_on": "2026-10-17",
        }
        bad = LetterForm({**fields, "assigned_to": self.bob.pk}, user=self.alice)
        self.assertFalse(bad.is_valid())
        self.assertIn("assigned_to", bad.errors)
        valid = LetterForm({**fields, "assigned_to": self.alice.pk}, user=self.alice)
        self.assertTrue(valid.is_valid(), valid.errors.as_text())

    def test_task_form_scopes_both_selected_unit_and_assignee(self):
        fields = {
            "title": "کنترل مواد", "priority": "normal",
            "unit": self.farm.pk, "assigned_to": self.alice.pk,
        }
        valid = TaskForm(fields, user=self.alice)
        self.assertTrue(valid.is_valid(), valid.errors.as_text())
        other_unit = TaskForm({**fields, "unit": self.factory.pk}, user=self.alice)
        self.assertFalse(other_unit.is_valid())
        self.assertIn("unit", other_unit.errors)
        outsider = TaskForm({**fields, "assigned_to": self.bob.pk}, user=self.alice)
        self.assertFalse(outsider.is_valid())
        self.assertIn("assigned_to", outsider.errors)

    def test_analyst_cannot_write_tasks_even_if_model_add_perm_was_granted(self):
        self.grant(self.alice, "add_worktask")
        self.client.force_login(self.alice)
        result = self.client.post(
            "/company/office/tasks/new/",
            {"title": "پیشنهاد بدون مجوز", "unit": self.farm.pk,
             "assigned_to": self.alice.pk, "priority": "normal"},
            secure=True,
        )
        self.assertEqual(result.status_code, 403)
        self.assertFalse(WorkTask.objects.exists())

    def test_worktask_admin_with_broad_model_permission_still_scoped_by_unit(self):
        self.grant(self.alice, "view_worktask", "change_worktask")
        farm_task = WorkTask.objects.create(
            title="فهرست مزرعه", assigned_to=self.alice,
            created_by=self.owner, unit=self.farm,
        )
        WorkTask.objects.create(
            title="برنامه کارخانه", assigned_to=self.bob,
            created_by=self.owner, unit=self.factory,
        )
        panel = admin.site._registry[WorkTask]
        req = self.request(self.alice, "/admin/enterprise_portal/worktask/")
        self.assertEqual(list(panel.get_queryset(req)), [farm_task])

    def test_meeting_admin_limits_reading_to_organizer_and_attendees(self):
        self.grant(self.alice, "view_meeting")
        now = timezone.now()
        hidden = Meeting.objects.create(
            title="جلسه خارج از واحد", agenda="محرمانه",
            starts_at=now, ends_at=now + timedelta(minutes=30),
            organizer=self.owner,
        )
        visible = Meeting.objects.create(
            title="جلسه مربوط", agenda="جلسه مشترک",
            starts_at=now, ends_at=now + timedelta(minutes=45),
            organizer=self.owner,
        )
        visible.attendees.add(self.alice)
        panel = admin.site._registry[Meeting]
        req = self.request(self.alice, "/admin/enterprise_portal/meeting/")
        self.assertEqual(list(panel.get_queryset(req)), [visible])
        self.assertFalse(panel.has_view_permission(req, hidden))
        self.assertTrue(panel.has_view_permission(req, visible))
        self.assertFalse(panel.has_change_permission(req, visible))

    def test_audit_log_records_are_private_to_actor_or_company_owner(self):
        self.grant(self.alice, "view_auditevent")
        hidden = AuditEvent.objects.create(
            actor=self.owner, action="journal_posted", target="JournalEntry:123",
            detail={"private_reference": "private-document"},
        )
        visible = AuditEvent.objects.create(
            actor=self.alice, action="office_task_created", target="WorkTask:234",
        )
        panel = admin.site._registry[AuditEvent]
        req = self.request(self.alice, "/admin/enterprise_portal/auditevent/")
        self.assertEqual(list(panel.get_queryset(req)), [visible])
        self.assertFalse(panel.has_view_permission(req, hidden))
        self.assertEqual(panel.get_queryset(self.request(self.owner, "/admin/")).count(), 2)
