"""Public main-targeted MOJ PROP Plan 1 customer-intake behavior."""
from urllib.parse import urlencode

from django.core import mail
from django.core.exceptions import ValidationError
from django.core.cache import cache
from django.contrib.admin.sites import site
from django.test import Client, TestCase, override_settings

from core.models import CommercialInterest, SignalInterest, Order, PaymentIntent


@override_settings(ALLOWED_HOSTS=[
    "mojplaywin.com","www.mojplaywin.com","zomorodmelal.ir",
])
class MojPropPublicIntakeTests(TestCase):
    URL="/moj-prop/interest/"
    BASE={
        "email":"Buyer@Example.com",
        "plan_code":"MOJ-PROP-01",
        "source_language":"en",
        "contact_consent":"yes",
        "consent_version":"moj-prop-interest-v1",
        "csrfmiddlewaretoken":"browser-managed",
    }
    def setUp(self):
        cache.clear()

    def post(self, fields=None, secure=True, host="mojplaywin.com", client=None):
        return (client or self.client).post(
            self.URL, data=urlencode(self.BASE if fields is None else fields),
            content_type="application/x-www-form-urlencoded",
            secure=secure, HTTP_HOST=host,
        )

    def test_public_plan_one_page_exists_on_mojplaywin(self):
        response=self.client.get("/moj-prop/",secure=True,HTTP_HOST="mojplaywin.com")
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'action="/moj-prop/interest/"')
        self.assertContains(response,'name="contact_consent"')
        self.assertContains(response,"30 TRX")
        self.assertContains(response,"No wallet address, invoice or trading account")
        self.assertIn("no-store",response["Cache-Control"])

    def test_localized_pages_are_real_not_language_guesses(self):
        for lang in ("fa","ar","de"):
            with self.subTest(lang=lang):
                response=self.client.get(f"/moj-prop/{lang}/",
                                         secure=True,HTTP_HOST="mojplaywin.com")
                self.assertEqual(response.status_code,200)
                self.assertContains(response,f'lang="{lang}"')
                self.assertContains(response,'name="consent_version"')

    def test_record_created_without_sale_or_trade(self):
        response=self.post()
        self.assertEqual(response.status_code,202)
        lead=CommercialInterest.objects.get()
        self.assertEqual(lead.offer_family,"moj_prop")
        self.assertEqual(lead.brand,"moj_prop")
        self.assertEqual(lead.plan_code,"MOJ-PROP-01")
        self.assertEqual(lead.email,"buyer@example.com")
        self.assertEqual(lead.source_host,"mojplaywin.com")
        self.assertEqual(lead.status,"new")
        self.assertEqual(PaymentIntent.objects.count(),0)
        self.assertEqual(Order.objects.count(),0)
        self.assertEqual(len(mail.outbox),0)

    def test_repeat_is_idempotent_and_never_reactivates_withdrawn(self):
        self.assertEqual(self.post().status_code,202)
        lead=CommercialInterest.objects.get()
        lead.status="withdrawn"
        lead.save(update_fields=("status","updated_at"))
        self.assertEqual(self.post().status_code,202)
        lead.refresh_from_db()
        self.assertEqual(lead.status,"withdrawn")
        self.assertEqual(CommercialInterest.objects.count(),1)

    def test_rejects_other_plans_and_missing_consent(self):
        for key,value in (
            ("plan_code","MOJ-PROP-02"),
            ("plan_code","MOJ-PROP-10"),
            ("contact_consent","no"),
            ("consent_version","made-up"),
            ("source_language","ru"),
            ("email","not-email"),
        ):
            with self.subTest(key=key,value=value):
                self.assertEqual(self.post({**self.BASE,key:value}).status_code,400)
        self.assertEqual(CommercialInterest.objects.count(),0)

    def test_https_and_tenant_are_not_optional(self):
        self.assertEqual(self.post(secure=False).status_code,404)
        self.assertEqual(self.post(host="zomorodmelal.ir").status_code,404)
        self.assertEqual(self.client.get("/moj-prop/",secure=True,
             HTTP_HOST="zomorodmelal.ir").status_code,404)
        self.assertEqual(CommercialInterest.objects.count(),0)

    def test_csrf_guest_is_enforced(self):
        browser=Client(enforce_csrf_checks=True)
        self.assertEqual(self.post(client=browser).status_code,403)
        self.assertEqual(CommercialInterest.objects.count(),0)

    def test_duplicate_field_and_unexpected_fields_rejected(self):
        duplicate=list(self.BASE.items())+[("plan_code","MOJ-PROP-02")]
        self.assertEqual(self.post(duplicate).status_code,400)
        self.assertEqual(self.post({**self.BASE,"paid": "true"}).status_code,400)
        self.assertEqual(CommercialInterest.objects.count(),0)

    def test_ninth_request_limited(self):
        for i in range(8):
            self.assertEqual(self.post().status_code,202)
        self.assertEqual(self.post().status_code,429)
        self.assertEqual(CommercialInterest.objects.count(),1)

    def test_get_does_not_write_or_offer_checkout(self):
        self.assertEqual(self.client.get(self.URL,secure=True,
             HTTP_HOST="mojplaywin.com").status_code,405)
        self.assertEqual(CommercialInterest.objects.count(),0)

    def test_same_email_in_signals_and_prop_is_two_authorized_requests(self):
        self.assertEqual(self.post().status_code,202)
        from core.signal_interest_policy import SIGNAL_PLAN_CODES
        record=SignalInterest(
            email="buyer@example.com", offer_family="signals", brand="saman",
            plan_code=SIGNAL_PLAN_CODES[0], consent_version="mojtaba-signals-interest-v1",
            source_language="en", source_host="mojplaywin.com",
        )
        record.save()
        self.assertEqual(CommercialInterest.objects.count(),2)
        self.assertEqual(set(CommercialInterest.objects.values_list(
            "offer_family",flat=True)),{"signals","moj_prop"})

    def test_superuser_only_unified_customer_desk(self):
        a=site._registry[CommercialInterest]
        self.assertFalse(a.has_add_permission(None))
        self.assertFalse(a.has_delete_permission(None))
        self.assertFalse(a.has_view_permission(None))
        self.assertFalse(a.has_change_permission(None))
        self.assertIn("offer_family",a.readonly_fields)

    def test_prop_terminal_consent_receipt(self):
        self.assertEqual(self.post().status_code, 202)
        lead = CommercialInterest.objects.get()
        lead.status = "withdrawn"
        lead.save(update_fields=["status", "updated_at"])
        lead.refresh_from_db()
        self.assertIsNotNone(lead.withdrawn_at)
        lead.status = "contacted"
        with self.assertRaises(ValidationError):
            lead.save(update_fields=["status", "updated_at"])
        lead.refresh_from_db()
        self.assertEqual(lead.status, "withdrawn")

    def test_prop_email_and_plan_provenance_unchangeable(self):
        self.post()
        for field, value in {
            "email": "elsewhere@example.org",
            "plan_code": "MOJ-PROP-02",
            "source_host": "www.mojplaywin.com",
            "source_language": "fa",
            "consent_version": "changed",
        }.items():
            with self.subTest(field=field):
                lead = CommercialInterest.objects.get()
                setattr(lead, field, value)
                with self.assertRaises(ValidationError):
                    lead.save()
        self.assertEqual(CommercialInterest.objects.get().plan_code, "MOJ-PROP-01")

    def test_prop_followup_status_then_withdrawn_has_no_money_side_effect(self):
        self.post()
        lead = CommercialInterest.objects.get()
        lead.status = "contacted"
        lead.save(update_fields=["status"])
        lead.status = "withdrawn"
        lead.save(update_fields=["status"])
        lead.refresh_from_db()
        self.assertIsNotNone(lead.withdrawn_at)
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(PaymentIntent.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 0)
