"""Contract tests for Plan 1 real interest acquisition, not payments."""
from urllib.parse import urlencode
from django.core import mail
from django.core.cache import cache
from django.contrib.admin.sites import site
from django.test import Client, TestCase, override_settings
from prop_firm.models import PropInterest
from core.models import Order, PaymentIntent
from prop_firm.models import PropAccount, PropChallengeEnrollment

@override_settings(ALLOWED_HOSTS=["mojplaywin.com","www.mojplaywin.com","zomorodmelal.ir"])
class PropInterestIntakeTests(TestCase):
    PATH = "/moj-prop/interest/"
    VALID = {
        "email": "Buyer@farmco.org",
        "plan_code": "MOJ-PROP-01",
        "consent_version": "moj-prop-interest-v1",
        "contact_consent": "yes",
        "source_language": "en",
    }

    def setUp(self):
        cache.clear()

    def post(self, data=None, secure=True, host="mojplaywin.com", client=None):
        body = urlencode(self.VALID if data is None else data)
        return (client or self.client).post(
            self.PATH, data=body, secure=secure, HTTP_HOST=host,
            content_type="application/x-www-form-urlencoded",
        )

    def test_intake_persists_one_prospect_but_zero_invoices_orders_or_enrollments(self):
        response = self.post()
        self.assertEqual(response.status_code, 202)
        lead = PropInterest.objects.get()
        self.assertEqual(lead.email, "buyer@farmco.org")
        self.assertEqual(lead.plan_code, "MOJ-PROP-01")
        self.assertEqual(lead.status, "new")
        self.assertEqual(lead.source_language, "en")
        self.assertEqual(lead.consent_version, "moj-prop-interest-v1")
        self.assertIn("private, no-store", response["Cache-Control"])
        self.assertIn("no-cache", response["Cache-Control"])
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(PaymentIntent.objects.count(), 0)
        self.assertEqual(PropAccount.objects.count(), 0)
        self.assertEqual(PropChallengeEnrollment.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_duplicate_email_does_not_duplicate_or_reinstate_withdrawn_record(self):
        self.assertEqual(self.post().status_code, 202)
        lead = PropInterest.objects.get()
        lead.status = "withdrawn"
        lead.save(update_fields=["status", "updated_at"])
        self.assertEqual(self.post(dict(self.VALID,email="buyer@farmco.org")).status_code, 202)
        lead.refresh_from_db()
        self.assertEqual(lead.status, "withdrawn")
        self.assertEqual(PropInterest.objects.count(), 1)

    def test_withdrawn_lead_cannot_be_reactivated_with_model_save(self):
        from django.core.exceptions import ValidationError
        self.assertEqual(self.post().status_code, 202)
        lead = PropInterest.objects.get()
        lead.status = "withdrawn"
        lead.save(update_fields=["status", "updated_at"])
        lead.status = "contacted"
        with self.assertRaises(ValidationError):
            lead.save(update_fields=["status", "updated_at"])
        lead.refresh_from_db()
        self.assertEqual(lead.status, "withdrawn")

    def test_withdrawn_lead_admin_model_form_validation_blocks_reset(self):
        from django.core.exceptions import ValidationError
        self.assertEqual(self.post().status_code, 202)
        lead = PropInterest.objects.get()
        lead.status = "withdrawn"
        lead.save(update_fields=["status"])
        lead.status = "new"
        with self.assertRaises(ValidationError):
            lead.full_clean()
        lead.refresh_from_db()
        self.assertEqual(lead.status, "withdrawn")

    def test_plan_one_followup_status_can_be_withdrawn(self):
        self.assertEqual(self.post().status_code, 202)
        lead = PropInterest.objects.get()
        lead.status = "contacted"
        lead.save(update_fields=["status"])
        lead.status = "withdrawn"
        lead.save(update_fields=["status"])
        lead.refresh_from_db()
        self.assertEqual(lead.status, "withdrawn")

    def test_refuse_missing_consent_and_wrong_plan(self):
        for name,value in (("contact_consent", "no"), ("plan_code", "MOJ-PROP-02"),
                           ("plan_code","MOJ-PROP-10"), ("consent_version", "bad"),
                           ("email", "bad-email"),("source_language","not-a-locale")):
            with self.subTest(value=value):
                self.assertEqual(self.post(dict(self.VALID,**{name:value})).status_code, 400)
        self.assertEqual(PropInterest.objects.count(), 0)

    def test_mojplaywin_https_is_required(self):
        self.assertEqual(self.post(secure=False).status_code, 404)
        self.assertEqual(self.post(host="zomorodmelal.ir").status_code, 404)
        self.assertEqual(PropInterest.objects.count(), 0)

    def test_get_cannot_mutate(self):
        self.assertEqual(self.client.get(self.PATH,secure=True,
                                       HTTP_HOST="mojplaywin.com").status_code,405)
        self.assertEqual(PropInterest.objects.count(),0)

    def test_csrf_protects_guest(self):
        guarded=Client(enforce_csrf_checks=True)
        self.assertEqual(self.post(client=guarded).status_code, 403)
        self.assertEqual(PropInterest.objects.count(),0)

    def test_localized_request_is_stored_without_email_send(self):
        self.assertEqual(self.post(dict(self.VALID, source_language="fa")).status_code,202)
        self.assertEqual(PropInterest.objects.get().source_language,"fa")
        self.assertEqual(len(mail.outbox),0)

    def test_excessive_requests_are_rate_limited(self):
        for _ in range(8):
            self.assertEqual(self.post().status_code,202)
        self.assertEqual(self.post().status_code,429)
        self.assertEqual(PropInterest.objects.count(),1)

    def test_query_set_cannot_bulk_reactivate_withdrawn_prop_consent(self):
        from django.core.exceptions import ValidationError
        self.assertEqual(self.post().status_code, 202)
        lead = PropInterest.objects.get()
        lead.status = "withdrawn"
        lead.save(update_fields=["status"])
        with self.assertRaises(ValidationError):
            PropInterest.objects.filter(pk=lead.pk).update(status="contacted")
        lead.refresh_from_db()
        self.assertEqual(lead.status, "withdrawn")

    def test_prop_bulk_update_cannot_revive_withdrawn_lead(self):
        from django.core.exceptions import ValidationError
        self.assertEqual(self.post().status_code, 202)
        lead = PropInterest.objects.get()
        lead.status = "withdrawn"
        lead.save(update_fields=["status"])
        lead.status = "new"
        with self.assertRaises(ValidationError):
            PropInterest.objects.bulk_update([lead], ["status"])
        lead.refresh_from_db()
        self.assertEqual(lead.status, "withdrawn")

    def test_bulk_withdrawal_can_only_mark_status_without_rewriting_identity(self):
        from django.core.exceptions import ValidationError
        self.assertEqual(self.post().status_code, 202)
        self.assertEqual(PropInterest.objects.all().update(status="withdrawn"), 1)
        lead = PropInterest.objects.get()
        self.assertEqual(lead.status, "withdrawn")
        with self.assertRaises(ValidationError):
            PropInterest.objects.filter(pk=lead.pk).update(
                status="withdrawn", email="somebody@farmco.org",
            )
        self.assertEqual(PropInterest.objects.get().email, "buyer@farmco.org")

    def test_reserved_email_domains_never_enter_prop_lead_inbox(self):
        for value in ("Buyer@Example.com", "buyer@example.org", "a@example.net",
                      "a@guest.mojplaywin.com", "a@host.invalid",
                      "a@internal.local", "a@host.test", "a@fake.example"):
            with self.subTest(address=value):
                self.assertEqual(self.post({**self.VALID, "email": value}).status_code, 400)
        self.assertEqual(PropInterest.objects.count(), 0)

    def test_unexpected_form_keys_and_duplicate_csrf_are_rejected(self):
        cases = [
            list(self.VALID.items()) + [("is_paid", "true")],
            list(self.VALID.items()) + [("csrfmiddlewaretoken", "a"),
                                        ("csrfmiddlewaretoken", "b")],
            list(self.VALID.items()) + [("email", "other@farmco.org")],
        ]
        for fields in cases:
            with self.subTest(fields=fields[-1]):
                self.assertEqual(self.post(fields).status_code, 400)
        self.assertEqual(PropInterest.objects.count(), 0)

    def test_critical_duplicate_fields_are_rejected(self):
        form = urlencode(list(self.VALID.items()) + [("plan_code","MOJ-PROP-02")])
        response=self.client.post(self.PATH, form,
            content_type="application/x-www-form-urlencoded",
            secure=True, HTTP_HOST="mojplaywin.com")
        self.assertEqual(response.status_code,400)
        self.assertEqual(PropInterest.objects.count(),0)

    @override_settings(STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    })
    def test_landing_form_is_real_consent_only_and_not_shared_cached(self):
        for path in ("/moj-prop/","/moj-prop/fa/","/moj-prop/ar/"):
            with self.subTest(path=path):
                response=self.client.get(path,HTTP_HOST="mojplaywin.com",secure=True)
                self.assertEqual(response.status_code,200)
                self.assertContains(response,'action="/moj-prop/interest/"')
                self.assertContains(response,'name="contact_consent"')
                self.assertContains(response,'name="source_language"')
                self.assertContains(response,'href="#plan-one-interest"')
                self.assertIn("private, no-store",response["Cache-Control"])
                self.assertIn("Cookie",response.get("Vary",""))

    def test_operator_inbox_is_registered_but_cannot_create_or_delete_lead(self):
        admin=site._registry[PropInterest]
        self.assertFalse(admin.has_add_permission(None))
        self.assertFalse(admin.has_delete_permission(None))
        self.assertEqual(admin.search_fields,("email",))
        self.assertFalse(admin.has_view_permission(None))
        self.assertFalse(admin.has_change_permission(None))
