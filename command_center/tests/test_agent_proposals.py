import json
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from core.models import Agent, ApprovalRequest

class AgentProposalTests(TestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_user(username="proposal_staff", password="test-only", is_staff=True)
        self.agent = Agent.objects.create(code="proposal-agent", name="Research", mission="Original", active=False)
        self.url = reverse("command_center_agent_proposals_api")

    def test_proposal_does_not_change_agent(self):
        self.staff.is_superuser = True
        self.staff.save(update_fields=["is_superuser"])
        self.client.force_login(self.staff)
        response = self.client.post(self.url, data=json.dumps({
            "agent_id": self.agent.pk, "field": "mission", "value": "New mission"
        }), content_type="application/json")
        self.assertEqual(response.status_code, 201)
        self.agent.refresh_from_db()
        self.assertEqual(self.agent.mission, "Original")
        self.assertEqual(ApprovalRequest.objects.filter(status="pending").count(), 1)

    def test_non_staff_cannot_submit(self):
        viewer = get_user_model().objects.create_user(username="proposal_viewer", password="test-only")
        self.client.force_login(viewer)
        response = self.client.post(self.url, data=json.dumps({
            "agent_id": self.agent.pk, "field": "active", "value": True
        }), content_type="application/json")
        self.assertNotEqual(response.status_code, 201)

    def test_staff_without_owner_role_is_forbidden(self):
        self.client.force_login(self.staff)
        response = self.client.post(self.url, data=json.dumps({
            "agent_id": self.agent.pk, "field": "mission", "value": "Other mission"
        }), content_type="application/json")
        self.assertEqual(response.status_code, 403)
        self.assertFalse(ApprovalRequest.objects.exists())
