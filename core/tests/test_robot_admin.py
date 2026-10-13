from django.contrib import admin
from django.test import SimpleTestCase

from core.models import Agent, AgentCapability, AgentTask, ApprovalRequest, Robot


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

    def test_robot_requires_explicit_runtime_qualification(self):
        robot = Robot(code="draft-robot", name="Draft")
        self.assertFalse(robot.runtime_enabled)
        robot.agent_id = 1
        robot.connector = "allowlisted_tool"
        robot.autonomy_level = "sandbox"
        robot.deployment_status = "sandbox"
        self.assertTrue(robot.runtime_enabled)

    def test_robot_admin_shows_linked_tasks_and_owner_approval_actions(self):
        robot_admin = admin.site._registry[Robot]
        self.assertEqual(len(robot_admin.inlines), 1)
        approval_admin = admin.site._registry[ApprovalRequest]
        self.assertIn("approve_owned_pending", approval_admin.actions)
        self.assertIn("reject_owned_pending", approval_admin.actions)
