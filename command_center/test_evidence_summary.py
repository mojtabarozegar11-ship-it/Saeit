"""The staff summaries distinguish reported completion from referenced outcomes."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from .models import WorkItem


class WorkEvidenceSummaryTests(TestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_user(
            username="evidence-reader", password="unused-test-credential", is_staff=True,
        )
        WorkItem.objects.create(title="Unreferenced completion", status="done",
                                resolution_reference="", created_by=self.staff)
        WorkItem.objects.create(title="Referenced but not verified", status="done",
                                resolution_reference="commit:example", created_by=self.staff)
        WorkItem.objects.create(title="Open item", status="open", created_by=self.staff)

    def test_operations_summary_marks_unverified_references(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("command_center_operations_summary_api"))
        self.assertEqual(response.status_code, 200)
        work = response.json()["work_items"]
        self.assertEqual(work["done"], 2)
        self.assertEqual(work["done_with_reference_unverified"], 1)
        self.assertEqual(work["done_without_reference"], 1)
        self.assertEqual(work["open"], 1)

    def test_management_report_marks_unverified_references(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("command_center_management_report_api"))
        self.assertEqual(response.status_code, 200)
        work = response.json()["work"]
        self.assertEqual(work["done"], 2)
        self.assertEqual(work["done_with_reference_unverified"], 1)
        self.assertEqual(work["done_without_reference"], 1)
