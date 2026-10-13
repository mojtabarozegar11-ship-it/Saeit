from django.contrib import admin
from django.test import SimpleTestCase

from core.models import Agent, AgentCapability, AgentTask, Robot


class AgentAndRobotAdminTests(SimpleTestCase):
    def test_agents_capabilities_tasks_and_robots_are_registered(self):
        for model in (Agent, AgentCapability, AgentTask, Robot):
            with self.subTest(model=model.__name__):
                self.assertIn(model, admin.site._registry)

    def test_robot_defaults_are_non_executing_and_require_owner_approval(self):
        robot = Robot(code="test-robot", name="Test robot")
        self.assertEqual(robot.autonomy_level, "observe")
        self.assertEqual(robot.deployment_status, "draft")
        self.assertTrue(robot.requires_owner_approval)
        self.assertEqual(robot.budget_limit, 0)

    def test_robot_secret_field_is_reference_only(self):
        field = Robot._meta.get_field("credential_reference")
        self.assertIn("Never store a credential", field.help_text)
