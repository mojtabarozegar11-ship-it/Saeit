from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

class ContentStatsTests(TestCase):
    def test_staff_can_read_counts(self):
        staff = get_user_model().objects.create_user(username="content_staff", password="test-only", is_staff=True)
        self.client.force_login(staff)
        response = self.client.get(reverse("command_center_content_stats_api"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("published_stories", response.json())
        self.assertFalse(response.json()["live_publishing_connected"])

    def test_non_staff_cannot_read(self):
        viewer = get_user_model().objects.create_user(username="content_viewer", password="test-only")
        self.client.force_login(viewer)
        response = self.client.get(reverse("command_center_content_stats_api"))
        self.assertNotEqual(response.status_code, 200)
