from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from core.models import ApprovalRequest

class ApprovalQueueTests(TestCase):
    def test_staff_sees_pending_without_mutation(self):
        staff = get_user_model().objects.create_user(username="queue_staff", password="test-only", is_staff=True)
        approval = ApprovalRequest.objects.create(
            action_type="agent_configuration_proposal", target_type="agent",
            target_id="1", reason="Change request", requested_by=staff, status="pending"
        )
        self.client.force_login(staff)
        response = self.client.get(reverse("command_center_pending_approvals_api"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["items"][0]["id"], approval.pk)
        approval.refresh_from_db()
        self.assertEqual(approval.status, "pending")

    def test_non_staff_is_denied(self):
        user = get_user_model().objects.create_user(username="queue_viewer", password="test-only")
        self.client.force_login(user)
        response = self.client.get(reverse("command_center_pending_approvals_api"))
        self.assertNotEqual(response.status_code, 200)
