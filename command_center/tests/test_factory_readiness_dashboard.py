from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class FactoryReadinessDashboardTests(TestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_user(
            username="factory_dashboard_staff",
            password="test-pass",
            is_staff=True,
        )
        self.client.force_login(self.staff)

    def test_factory_stages_remain_unknown_without_evidence(self):
        response = self.client.get(reverse("command_center_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-factory-stage="plan"')
        self.assertContains(response, 'data-factory-stage="approval"')
        self.assertContains(response, 'data-factory-stage="task"')
        self.assertContains(response, 'data-factory-stage="claim"')
        self.assertContains(response, 'data-factory-stage="complete"')
        self.assertContains(response, 'data-factory-stage="audit"')
        self.assertContains(response, "شاهد متصل نیست")

    def test_master_agent_workspaces_are_separate_and_disconnected(self):
        response = self.client.get(reverse("command_center_dashboard"))
        self.assertEqual(response.status_code, 200)
        for section_id in (
            "master-agent-factory",
            "master-agent-zomorod",
            "master-agent-mojplaywin",
        ):
            self.assertContains(response, f'id="{section_id}"')
        self.assertContains(response, "ارسال دستور و اجرای عملیات در این صفحه غیرفعال است")
        self.assertNotContains(response, 'name="master-agent-message"')

    def test_settings_explain_owner_approval(self):
        response = self.client.get(reverse("command_center_dashboard"))
        self.assertContains(response, "عملیات حساس تا زمان اتصال مسیر اجرایی، فقط با تأیید مالک مجاز است")

    def test_non_staff_cannot_open_dashboard(self):
        viewer = get_user_model().objects.create_user(
            username="factory_dashboard_viewer",
            password="test-pass",
            is_staff=False,
        )
        self.client.force_login(viewer)
        response = self.client.get(reverse("command_center_dashboard"))
        self.assertNotEqual(response.status_code, 200)
