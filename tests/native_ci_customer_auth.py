"""Private MySQL-compatible auth test, never changes a real user database."""
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse


@override_settings(ALLOWED_HOSTS=["mojplaywin.com", "www.mojplaywin.com", "zomorodmelal.ir"])
class CustomerAuthTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.login_url = reverse("mpw_commerce:customer_login")
        self.register_url = reverse("mpw_commerce:customer_register")

    def get(self, url, host="mojplaywin.com", secure=True):
        return self.client.get(url, HTTP_HOST=host, secure=secure)

    def test_login_page_on_mojplaywin(self):
        result = self.get(self.login_url)
        self.assertEqual(result.status_code, 200)
        self.assertContains(result, "Sign in")
        self.assertContains(result, self.register_url)

    def test_registration_creates_nonstaff_buyer_and_authenticates(self):
        result = self.client.post(
            self.register_url,
            {"username": "first-mpw-buyer", "password1": "UncommonBuyer@2026!1",
             "password2": "UncommonBuyer@2026!1"},
            secure=True, HTTP_HOST="mojplaywin.com",
        )
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"], "/commerce/my-purchases/")
        buyer = get_user_model().objects.get(username="first-mpw-buyer")
        self.assertFalse(buyer.is_staff)
        self.assertFalse(buyer.is_superuser)
        self.assertIn("_auth_user_id", self.client.session)

    def test_strict_host_and_tls(self):
        self.assertEqual(self.get(self.login_url, host="zomorodmelal.ir").status_code, 404)
        self.assertEqual(self.get(self.register_url, host="zomorodmelal.ir").status_code, 404)
        self.assertEqual(self.get(self.login_url, secure=False).status_code, 404)
        self.assertEqual(self.get(self.register_url, secure=False).status_code, 404)

    def test_invalid_registration_does_not_create_account(self):
        self.client.post(
            self.register_url,
            {"username": "bad-mpw-buyer", "password1": "abc", "password2": "abc"},
            secure=True, HTTP_HOST="mojplaywin.com",
        )
        self.assertFalse(get_user_model().objects.filter(username="bad-mpw-buyer").exists())
