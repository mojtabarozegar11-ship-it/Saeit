from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class BusinessOperatingReviewAPITests(TestCase):
    def setUp(self):
        self.url = reverse("command_center_business_operating_api")

    def test_anonymous_cannot_read_sensitive_operating_metrics(self):
        response = self.client.get(self.url)
        self.assertNotEqual(response.status_code, 200)

    def test_staff_gets_scoped_non_cached_evidence(self):
        user = get_user_model().objects.create_user(username="staff-review", password="test-only", is_staff=True)
        self.client.force_login(user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "no-store")
        payload = response.json()
        self.assertEqual(payload["metrics"]["verified_collected_cash"]["state"], "unknown")
        self.assertIn("local_django_database_only", payload["scope"])
