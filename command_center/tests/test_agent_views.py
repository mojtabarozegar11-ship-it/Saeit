from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from core.models import Agent, AgentTask

class AgentMetricsTests(TestCase):
    def test_staff_sees_database_counts(self):
        user = get_user_model().objects.create_user(username="staff_metrics", password="test-pass", is_staff=True)
        agent = Agent.objects.create(code="metrics-agent", name="Metrics", mission="Count", active=True)
        AgentTask.objects.create(agent=agent, status="queued")
        self.client.force_login(user)
        response = self.client.get(reverse("command_center_agent_metrics_api"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["agents"]["enabled"], 1)
        self.assertEqual(response.json()["tasks"]["queued"], 1)
        self.assertEqual(response.json()["runtime_health"], "unknown")

    def test_non_staff_denied(self):
        user = get_user_model().objects.create_user(username="viewer_metrics", password="test-pass")
        self.client.force_login(user)
        response = self.client.get(reverse("command_center_agent_metrics_api"))
        self.assertNotEqual(response.status_code, 200)
