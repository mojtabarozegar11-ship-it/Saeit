from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from core.models import Agent, AgentTask


class ZomorodEvidenceTests(TestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_user(
            username="zomorod_evidence_staff", password="test-password", is_staff=True,
        )
        self.agent = Agent.objects.create(code="zomorod-probe", name="Evidence", mission="Report")

    def test_task_counts_are_real_but_not_live_heartbeat(self):
        AgentTask.objects.create(agent=self.agent, status="completed")
        AgentTask.objects.create(agent=self.agent, status="failed")
        self.client.force_login(self.staff)
        data = self.client.get(reverse("command_center_agent_metrics_api")).json()
        self.assertEqual(data["tasks"]["completed"], 1)
        self.assertEqual(data["tasks"]["failed"], 1)
        self.assertEqual(data["runtime_health"], "unknown")
        self.assertFalse(data["live_connected"])
        record = next(a for a in data["per_agent"] if a["code"] == "zomorod-probe")
        self.assertEqual(record["tasks_total"], 2)
        self.assertFalse(record["live_worker_verified"])

    def test_overview_progress_never_fabricated(self):
        AgentTask.objects.create(agent=self.agent, status="completed")
        self.client.force_login(self.staff)
        result = self.client.get(reverse("command_center_overview_api"))
        self.assertEqual(result.status_code, 200)
        data = result.json()
        self.assertEqual(data["workstreams"]["django_agent_tasks"]["completed"], 1)
        self.assertEqual(data["workstreams"]["django_agent_tasks"]["verified"], 0)
        self.assertFalse(data["live_connected"])
        self.assertEqual(data["health"]["overall"], "unknown")
        self.assertEqual(data["expected_components"][0]["state"], "unknown")

    def test_non_staff_cannot_read_snapshot(self):
        user = get_user_model().objects.create_user(
            username="zomorod_probe_viewer", password="test-password",
        )
        self.client.force_login(user)
        self.assertNotEqual(
            self.client.get(reverse("command_center_overview_api")).status_code, 200
        )
