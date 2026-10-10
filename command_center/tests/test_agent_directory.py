from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from core.models import Agent

class DirectoryTests(TestCase):
    def test_staff_can_read_agent_configuration(self):
        staff = get_user_model().objects.create_user(username="staff_dir", password="test-password", is_staff=True)
        Agent.objects.create(code="test-dir-agent", name="Research", mission="Research sources", active=False)
        self.client.force_login(staff)
        result = self.client.get(reverse("command_center_agent_directory_api"))
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["agents"][0]["code"], "test-dir-agent")

    def test_non_staff_cannot_read_directory(self):
        viewer = get_user_model().objects.create_user(username="viewer_dir", password="test-password")
        self.client.force_login(viewer)
        result = self.client.get(reverse("command_center_agent_directory_api"))
        self.assertNotEqual(result.status_code, 200)
