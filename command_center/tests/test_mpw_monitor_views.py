from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse


@override_settings(ALLOWED_HOSTS=["mojplaywin.com", "zomorodmelal.ir", "testserver"])
class PrivateMpwMonitorTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="mpw-monitor-staff", password="test-pass", is_staff=True)
        self.viewer = get_user_model().objects.create_user(
            username="mpw-monitor-viewer", password="test-pass")
        self.path = reverse("mpw_agent_monitor")
        self.api = reverse("mpw_agent_monitor_api")

    def test_staff_only_view_and_api(self):
        self.client.force_login(self.user)
        with patch("command_center.mpw_monitor_views.snapshot", return_value={
            "tenant": "mojplaywin-main", "items": [], "summary": {}, "source": "private_cpanel_unavailable"
        }):
            response = self.client.get(self.api, HTTP_HOST="mojplaywin.com")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["items"], [])
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(response["X-Robots-Tag"], "noindex, nofollow")
        self.assertEqual(self.client.get(self.path, HTTP_HOST="mojplaywin.com").status_code, 200)

    def test_other_domains_are_denied(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(self.api, HTTP_HOST="zomorodmelal.ir").status_code, 404)
        self.assertEqual(self.client.get(self.path, HTTP_HOST="zomorodmelal.ir").status_code, 404)

    def test_nonstaff_must_not_receive_private_data(self):
        self.client.force_login(self.viewer)
        self.assertNotEqual(self.client.get(self.api, HTTP_HOST="mojplaywin.com").status_code, 200)
        self.client.logout()
        self.assertNotEqual(self.client.get(self.api, HTTP_HOST="mojplaywin.com").status_code, 200)

    def test_no_write_methods(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.post(self.api, HTTP_HOST="mojplaywin.com").status_code, 405)
