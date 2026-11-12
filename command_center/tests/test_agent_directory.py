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
        data = result.json()
        self.assertEqual(data["bot"]["identity"], "mojtaba.bot.ai")
        self.assertEqual(data["bot"]["identity_count"], 1)
        self.assertIsNone(data["bot"]["runtime_verified"])
        self.assertIn("test-dir-agent", [module["module_code"] for module in data["modules"]])
        self.assertTrue(all(module["verification_state"] == "unknown" for module in data["modules"]))
        self.assertIn("agents", data)  # Legacy API remains readable until clients migrate.
        canonical = self.client.get(reverse("command_center_unified_bot_modules_api"))
        self.assertEqual(canonical.status_code, 200)
        self.assertEqual(canonical.json()["bot"]["identity"], "mojtaba.bot.ai")
        self.assertNotIn("agents", canonical.json())

    def test_invalid_offset_rejected(self):
        staff = get_user_model().objects.create_user(username="invalid_offset_staff", password="test-password", is_staff=True)
        self.client.force_login(staff)
        response = self.client.get(reverse("command_center_unified_bot_modules_api") + "?offset=-1")
        self.assertEqual(response.status_code, 400)

    def test_non_staff_cannot_read_directory(self):
        viewer = get_user_model().objects.create_user(username="viewer_dir", password="test-password")
        self.client.force_login(viewer)
        result = self.client.get(reverse("command_center_agent_directory_api"))
        self.assertNotEqual(result.status_code, 200)
