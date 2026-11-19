from datetime import timedelta
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from prop_firm.models import PropSimulationIdentity, PropSimulationLoginChallenge
from prop_firm.simulation_identity import issue_challenge, consume_challenge, is_verified_simulation_user

@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    MPW_SIMULATION_IDENTITY_ENABLED=True, MPW_SIMULATION_FROM_EMAIL="support@mojplaywin.com",
    ALLOWED_HOSTS=["mojplaywin.com", "zomorodmelal.ir"])
class CustomerIdentityTests(TestCase):
    def setUp(self):
        cache.clear()
        self.email = "buyer@farmco.org"

    def test_challenge_is_hashed_and_single_use(self):
        identifier, code = issue_challenge(self.email)
        row = PropSimulationLoginChallenge.objects.get(email=self.email)
        self.assertNotEqual(row.code_digest, code)
        self.assertEqual(len(row.code_digest), 64)
        self.assertIsNone(issue_challenge(self.email))
        owner = consume_challenge(identifier, code)
        self.assertTrue(is_verified_simulation_user(owner))
        self.assertFalse(owner.has_usable_password())
        self.assertIsNone(consume_challenge(identifier, code))
        self.assertEqual(PropSimulationIdentity.objects.count(), 1)

    def test_expired_and_bruteforced_codes_are_refused(self):
        identifier, code = issue_challenge(self.email)
        wrong = "A"*12 if code != "A"*12 else "B"*12
        for _ in range(5):
            self.assertIsNone(consume_challenge(identifier, wrong))
        self.assertIsNone(consume_challenge(identifier, code))
        PropSimulationLoginChallenge.objects.update(sent_at=timezone.now()-timedelta(minutes=3))
        identifier, code = issue_challenge(self.email)
        PropSimulationLoginChallenge.objects.update(expires_at=timezone.now()-timedelta(seconds=1))
        self.assertIsNone(consume_challenge(identifier, code))

    def test_recovery_reuses_only_dedicated_identity(self):
        staff = get_user_model().objects.create_user(username="staff", email=self.email, is_staff=True)
        identifier, code = issue_challenge(self.email)
        customer = consume_challenge(identifier, code)
        self.assertNotEqual(staff.pk, customer.pk)
        self.assertFalse(is_verified_simulation_user(staff))
        PropSimulationLoginChallenge.objects.update(sent_at=timezone.now()-timedelta(minutes=3))
        identifier, code = issue_challenge(self.email)
        self.assertEqual(consume_challenge(identifier, code).pk, customer.pk)

    def test_http_login_and_session_binding(self):
        path = "/moj-prop/account/login/"
        self.assertEqual(self.client.post(path, {"action":"request","email":self.email}, secure=True,
            HTTP_HOST="mojplaywin.com").status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        code = mail.outbox[0].body.split("Your sign-in code is ")[1].split(".")[0]
        from django.test import Client
        outsider = Client()
        self.assertEqual(outsider.post(path, {"action":"confirm","code":code}, secure=True,
            HTTP_HOST="mojplaywin.com").status_code, 200)
        self.assertNotIn("_auth_user_id", outsider.session)
        self.assertEqual(self.client.post(path, {"action":"confirm","code":code}, secure=True,
            HTTP_HOST="mojplaywin.com").status_code, 302)
        self.assertIn("_auth_user_id", self.client.session)

    def test_host_and_https_gates(self):
        path = "/moj-prop/account/login/"
        self.assertEqual(self.client.get(path, secure=True, HTTP_HOST="zomorodmelal.ir").status_code, 404)
        self.assertEqual(self.client.get(path, secure=False, HTTP_HOST="mojplaywin.com").status_code, 404)
        with override_settings(MPW_SIMULATION_IDENTITY_ENABLED=False):
            self.assertEqual(self.client.get(path, secure=True, HTTP_HOST="mojplaywin.com").status_code, 404)
