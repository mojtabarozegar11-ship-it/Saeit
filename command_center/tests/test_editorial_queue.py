from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

class EditorialQueueTests(TestCase):
    def test_staff_can_read_queue(self):
        staff = get_user_model().objects.create_user(username="editor_staff", password="test-only", is_staff=True)
        self.client.force_login(staff)
        response = self.client.get(reverse("command_center_editorial_queue_api"))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["read_only"])
        self.assertIn("items", response.json())

    def test_non_staff_denied(self):
        viewer = get_user_model().objects.create_user(username="editor_viewer", password="test-only")
        self.client.force_login(viewer)
        response = self.client.get(reverse("command_center_editorial_queue_api"))
        self.assertNotEqual(response.status_code, 200)
