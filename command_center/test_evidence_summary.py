"""The staff summaries distinguish reported completion from referenced outcomes."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from .models import WorkItem
from .integrated_ledger_api import cycle_health


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

    def test_command_cycle_requires_50_report_slots_specialists_20(self):
        coverage = {item["project"]: item for item in cycle_health()["coverage"]}
        self.assertEqual(coverage["management"]["minimum_reports_per_cycle"], 50)
        self.assertEqual(coverage["mojplaywin"]["minimum_reports_per_cycle"], 20)
        self.assertEqual(coverage["management"]["reports_needed_for_minimum"], 2500)
        self.assertEqual(coverage["mojplaywin"]["reports_needed_for_minimum"], 1000)
        # Report count is not independently verified completed work.
        self.assertIsNone(cycle_health()["verified_completions"])

