"""Private Zomorod task lifecycle: assignment, evidence, review, and audit."""
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import Client, TestCase, override_settings

from enterprise_portal.models import (
    AuditEvent, BusinessUnit, JournalEntry, StockMovement, WorkTask,
)
from ecosystem_hub.models import UnitMembership


STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


@override_settings(
    STORAGES=STORAGES, DEBUG=False, ALLOWED_HOSTS=["testserver"],
    COMPANY_OFFICE_REQUIRE_MFA=False,
)
class HumanTaskWorkflowTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_superuser(
            username="workflow-owner", email="wf@example.org", password="test-only",
        )
        self.manager = User.objects.create_user(
            username="workflow-manager", is_staff=True, password="test-only",
        )
        self.worker = User.objects.create_user(
            username="workflow-worker", is_staff=True, password="test-only",
        )
        self.outsider = User.objects.create_user(
            username="workflow-outsider", is_staff=True, password="test-only",
        )
        self.colleague = User.objects.create_user(
            username="workflow-colleague", is_staff=True, password="test-only",
        )
        self.farm = BusinessUnit.objects.create(code="farm", name="کشاورزی")
        self.factory = BusinessUnit.objects.create(code="factory", name="صنعت")
        for user in (self.manager, self.worker, self.colleague):
            UnitMembership.objects.create(user=user, unit=self.farm, role="manager" if user == self.manager else "analyst")
        UnitMembership.objects.create(user=self.outsider, unit=self.factory, role="manager")
        view_perms = list(Permission.objects.filter(
            content_type__app_label="enterprise_portal",
            codename__in=("view_businessunit", "view_worktask"),
        ))
        change_perm = Permission.objects.get(
            content_type__app_label="enterprise_portal", codename="change_worktask",
        )
        for user in (self.worker, self.manager, self.outsider, self.colleague):
            user.user_permissions.add(*view_perms)
        for user in (self.manager, self.outsider):
            user.user_permissions.add(change_perm)
        self.task = WorkTask.objects.create(
            unit=self.farm, title="پیگیری فروش زمرد",
            assigned_to=self.worker, created_by=self.manager, priority="high",
            status="todo",
        )
        self.path = f"/company/office/tasks/{self.task.pk}/"

    def post(self, user, code, expected, *, note="شواهد ثبت و بررسی شد", path=None):
        self.client.force_login(user)
        return self.client.post(path or self.path, {
            "transition": code, "expected_status": expected, "note": note,
        }, secure=True)

    def test_private_detail_get_is_read_only_and_actions_match_assignee(self):
        self.client.force_login(self.worker)
        response = self.client.get(self.path, secure=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "پیگیری فروش زمرد")
        self.assertContains(response, "شروع کار")
        self.assertNotContains(response, ">تأیید تکمیل</button>")
        self.assertEqual(self.task.status, "todo")
        self.assertFalse(AuditEvent.objects.exists())
        self.assertIn("no-store", response["Cache-Control"])
        listing = self.client.get("/company/office/tasks/", secure=True)
        self.assertContains(listing, self.path)

    def test_assignee_submits_and_separate_manager_approves_with_audit(self):
        self.assertEqual(self.post(self.worker, "start", "todo").status_code, 302)
        self.assertEqual(self.post(self.worker, "submit", "doing").status_code, 302)
        self.assertEqual(self.post(self.worker, "approve", "review").status_code, 403)
        self.assertEqual(self.post(self.manager, "approve", "review").status_code, 302)
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, "done")
        events = list(AuditEvent.objects.order_by("pk"))
        self.assertEqual([x.detail["transition"] for x in events],
                         ["start", "submit", "approve"])
        self.assertEqual([x.detail["to"] for x in events],
                         ["doing", "review", "done"])
        self.assertTrue(all(x.detail["no_external_side_effects"] for x in events))
        self.assertTrue(all(x.detail["human_action"] for x in events))
        self.assertFalse(JournalEntry.objects.exists())
        self.assertFalse(StockMovement.objects.exists())

    def test_rework_requires_reason_and_worker_resubmits(self):
        self.post(self.worker, "start", "todo")
        self.post(self.worker, "submit", "doing")
        self.assertEqual(self.post(self.manager, "rework", "review",
                                   note="مدرک کافی نیست").status_code, 302)
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, "doing")
        self.assertEqual(self.post(self.worker, "submit", "doing",
                                   note="اصلاح و تکمیل شد").status_code, 302)
        self.assertEqual(self.post(self.manager, "approve", "review",
                                   note="شواهد پذیرفته شد").status_code, 302)
        self.assertEqual(AuditEvent.objects.count(), 5)
        self.assertTrue(AuditEvent.objects.filter(
            detail__transition="rework",
        ).exists())

    def test_self_review_is_denied_except_audited_superuser_override(self):
        own = WorkTask.objects.create(
            unit=self.farm, title="مأموریت مدیر",
            assigned_to=self.manager, created_by=self.manager,
        )
        own_path = f"/company/office/tasks/{own.pk}/"
        self.post(self.manager, "start", "todo", path=own_path)
        self.post(self.manager, "submit", "doing", path=own_path)
        self.assertEqual(self.post(self.manager, "approve", "review",
                                   path=own_path).status_code, 403)
        self.assertEqual(self.post(self.owner, "approve", "review",
                                   path=own_path).status_code, 302)
        own.refresh_from_db()
        self.assertEqual(own.status, "done")
        final = AuditEvent.objects.filter(target=f"WorkTask:{own.pk}").order_by("-pk").first()
        self.assertEqual(final.detail["transition"], "approve")
        self.assertFalse(final.detail["superuser_self_review_override"])

    def test_staff_cannot_read_other_units_or_colleague_private_task(self):
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(self.path, secure=True).status_code, 404)
        denied = self.post(self.outsider, "start", "todo")
        self.assertEqual(denied.status_code, 404)
        other = WorkTask.objects.create(
            unit=self.farm, title="محرمانه کارمند دیگر",
            assigned_to=self.colleague, created_by=self.owner,
        )
        self.client.force_login(self.worker)
        self.assertEqual(self.client.get(
            f"/company/office/tasks/{other.pk}/", secure=True,
        ).status_code, 404)
        self.assertFalse(AuditEvent.objects.exists())

    def test_replay_stale_form_invalid_codes_and_short_evidence_fail_closed(self):
        self.assertEqual(self.post(self.worker, "start", "todo").status_code, 302)
        self.assertEqual(self.post(self.worker, "start", "todo").status_code, 409)
        self.assertEqual(self.post(self.worker, "approve", "doing").status_code, 403)
        self.assertEqual(self.post(self.worker, "bad-action", "doing").status_code, 400)
        self.assertEqual(self.post(self.worker, "submit", "doing", note="bad").status_code, 400)
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, "doing")
        self.assertEqual(AuditEvent.objects.count(), 1)

    def test_tls_csrf_anonymous_and_get_only_guards(self):
        self.assertEqual(self.client.get(self.path, secure=True).status_code, 302)
        self.client.force_login(self.worker)
        self.assertEqual(self.client.get(self.path).status_code, 403)
        self.assertEqual(self.client.post(self.path, {
            "transition": "start", "expected_status": "todo",
            "note": "شروع مجاز تست",
        }).status_code, 403)
        browser = Client(enforce_csrf_checks=True)
        browser.force_login(self.worker)
        self.assertEqual(browser.post(self.path, {
            "transition": "start", "expected_status": "todo",
            "note": "شروع مجاز تست",
        }, secure=True).status_code, 403)
        self.assertFalse(AuditEvent.objects.exists())
