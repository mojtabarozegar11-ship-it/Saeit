from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

class EditorialDetailTests(TestCase):
    def test_missing_story_is_404_for_staff(self):
        staff = get_user_model().objects.create_user(username="detail_staff", password="test-only", is_staff=True)
        self.client.force_login(staff)
        response = self.client.get(reverse("command_center_editorial_detail_api", args=[999999999]))
        self.assertEqual(response.status_code, 404)

    def test_non_staff_cannot_read(self):
        viewer = get_user_model().objects.create_user(username="detail_viewer", password="test-only")
        self.client.force_login(viewer)
        response = self.client.get(reverse("command_center_editorial_detail_api", args=[1]))
        self.assertNotEqual(response.status_code, 200)
