"""Genuine DB writes and tamper-proof contact-only signal funnel tests."""
from urllib.parse import urlencode
from types import SimpleNamespace
from django.core import mail
from django.core.exceptions import ValidationError
from django.core.cache import cache
from django.contrib.admin.sites import site
from django.test import Client, TestCase, override_settings
from core.signal_interest_models import SignalInterest
from core.signal_interest_policy import SIGNAL_BRANDS, CANONICAL_AGENT
from core.models import Order, PaymentIntent


@override_settings(ALLOWED_HOSTS=[
    "mojplaywin.com", "www.mojplaywin.com", "zomorodmelal.ir",
    "www.zomorodmelal.ir", "example.org",
])
class SignalInterestIntakeTests(TestCase):
    URL = "/market-signals/interest/"
    BASE = {
        "email":"Client@Example.org",
        "brand":"saman",
        "plan_code":"moj-signals-standard",
        "source_language":"en",
        "contact_consent":"yes",
        "consent_version":"mojtaba-signals-interest-v1",
        "csrfmiddlewaretoken":"browser-managed",
    }
    def setUp(self):
        cache.clear()

    def post(self, data=None, host="mojplaywin.com", secure=True, client=None):
        return (client or self.client).post(
            self.URL, data=urlencode(self.BASE if data is None else data),
            HTTP_HOST=host, secure=secure,
            content_type="application/x-www-form-urlencoded",
        )

    def test_real_db_contact_no_invoice_or_mail(self):
        response = self.post()
        self.assertEqual(response.status_code,202)
        lead = SignalInterest.objects.get()
        self.assertEqual(lead.email,"client@example.org")
        self.assertEqual(lead.brand,"saman")
        self.assertEqual(lead.plan_code,"moj-signals-standard")
        self.assertEqual(lead.status,"new")
        self.assertEqual(Order.objects.count(),0)
        self.assertEqual(PaymentIntent.objects.count(),0)
        self.assertEqual(len(mail.outbox),0)

    def test_repeated_optin_idempotent_and_no_revive(self):
        self.assertEqual(self.post().status_code,202)
        lead=SignalInterest.objects.get()
        lead.status="withdrawn"
        lead.save(update_fields=["status","updated_at"])
        self.assertEqual(self.post().status_code,202)
        lead.refresh_from_db()
        self.assertEqual(lead.status,"withdrawn")
        self.assertEqual(SignalInterest.objects.count(),1)

    def test_different_brand_and_package_produce_distinct_provenance(self):
        self.assertEqual(self.post().status_code,202)
        self.assertEqual(self.post({**self.BASE,"brand":"zahra"}).status_code,202)
        self.assertEqual(self.post({**self.BASE,"plan_code":"moj-signals-plus"}).status_code,202)
        self.assertEqual(SignalInterest.objects.count(),3)

    def test_all_17_brands_have_same_canonical_bot_and_real_optin(self):
        self.assertEqual(len(SIGNAL_BRANDS),17)
        self.assertEqual(CANONICAL_AGENT,"mojtaba.bot.ai")
        for brand in SIGNAL_BRANDS:
            with self.subTest(brand=brand):
                response=self.client.get(f"/{brand}/market-signals/",
                        secure=True,HTTP_HOST="mojplaywin.com")
                self.assertEqual(response.status_code,200)
                self.assertContains(response,'action="/market-signals/interest/"')
                self.assertContains(response,f'value="{brand}"')
                self.assertContains(response,"mojtaba.bot.ai")
                self.assertEqual(response["Cache-Control"],"private, no-store, max-age=0")

    def test_zomorod_rtl_source_is_preserved(self):
        response=self.client.get("/saman/market-signals/",
                                 secure=True,HTTP_HOST="zomorodmelal.ir")
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'lang="fa"')
        self.assertContains(response,'action="/market-signals/interest/"')
        self.assertEqual(self.post({**self.BASE,"source_language":"fa"},
                                   host="zomorodmelal.ir").status_code,202)
        self.assertEqual(SignalInterest.objects.get().source_host,"zomorodmelal.ir")
        self.assertEqual(SignalInterest.objects.get().source_language,"fa")

    def test_arabic_route_supported(self):
        response=self.client.get("/ar/saman/market-signals/",
                                 secure=True,HTTP_HOST="mojplaywin.com")
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'lang="ar"')
        self.assertEqual(self.post({**self.BASE,"source_language":"ar"}).status_code,202)

    def test_wrong_host_and_http_rejected(self):
        self.assertEqual(self.post(host="example.org").status_code,404)
        self.assertEqual(self.post(secure=False).status_code,404)
        self.assertEqual(SignalInterest.objects.count(),0)

    def test_no_consent_bad_sku_bad_email_rejected(self):
        cases=[
            ("contact_consent","no"),("plan_code","moj-prop-01"),
            ("brand","unknown"),("source_language","de"),
            ("consent_version","bogus"),("email","invalid"),
        ]
        for field,value in cases:
            with self.subTest(field=field,value=value):
                self.assertEqual(self.post({**self.BASE,field:value}).status_code,400)
        self.assertEqual(SignalInterest.objects.count(),0)

    def test_duplicate_sensitive_field_rejected(self):
        data=list(self.BASE.items())+[("brand","zahra")]
        self.assertEqual(self.post(data).status_code,400)
        self.assertEqual(SignalInterest.objects.count(),0)

    def test_csrf_checked_on_guest_request(self):
        guarded=Client(enforce_csrf_checks=True)
        self.assertEqual(self.post(client=guarded).status_code,403)
        self.assertEqual(SignalInterest.objects.count(),0)

    def test_get_never_writes(self):
        self.assertEqual(self.client.get(self.URL,secure=True,
                         HTTP_HOST="mojplaywin.com").status_code,405)
        self.assertEqual(SignalInterest.objects.count(),0)

    def test_rate_limiting_rejects_ninth_request(self):
        for _ in range(8):
            self.assertEqual(self.post().status_code,202)
        self.assertEqual(self.post().status_code,429)
        self.assertEqual(SignalInterest.objects.count(),1)

    def test_superuser_only_admin(self):
        a=site._registry[SignalInterest]
        self.assertFalse(a.has_view_permission(None))
        self.assertFalse(a.has_change_permission(None))
        self.assertFalse(a.has_add_permission(None))
        self.assertFalse(a.has_delete_permission(None))
        self.assertIn("email",a.readonly_fields)

    def test_withdrawn_timestamp_cannot_be_reactivated(self):
        self.assertEqual(self.post().status_code, 202)
        lead = SignalInterest.objects.get()
        self.assertIsNone(lead.withdrawn_at)
        lead.status = "withdrawn"
        lead.save(update_fields=["status", "updated_at"])
        lead.refresh_from_db()
        self.assertIsNotNone(lead.withdrawn_at)
        original_stamp = lead.withdrawn_at
        lead.status = "new"
        with self.assertRaises(ValidationError):
            lead.save(update_fields=["status", "updated_at"])
        lead.refresh_from_db()
        self.assertEqual(lead.status, "withdrawn")
        self.assertEqual(lead.withdrawn_at, original_stamp)

    def test_contacted_can_transition_to_withdrawn_but_never_back(self):
        self.post()
        lead = SignalInterest.objects.get()
        lead.status = "contacted"
        lead.save(update_fields=["status", "updated_at"])
        lead.refresh_from_db()
        self.assertEqual(lead.status, "contacted")
        self.assertIsNone(lead.withdrawn_at)
        lead.status = "withdrawn"
        lead.save(update_fields=["status", "updated_at"])
        lead.refresh_from_db()
        self.assertIsNotNone(lead.withdrawn_at)
        lead.status = "contacted"
        with self.assertRaises(ValidationError):
            lead.save()

    def test_source_consent_fields_are_immutable_after_intake(self):
        self.post()
        changes = {
            "email": "other@example.org", "brand": "zahra",
            "plan_code": "moj-signals-plus", "consent_version": "unverified",
            "source_language": "ar", "source_host": "zomorodmelal.ir",
            "offer_family": "moj_prop",
        }
        for field, value in changes.items():
            with self.subTest(field=field):
                lead = SignalInterest.objects.get()
                setattr(lead, field, value)
                with self.assertRaises(ValidationError):
                    lead.save()
        lead = SignalInterest.objects.get()
        self.assertEqual(lead.offer_family, "signals")
        self.assertEqual(lead.source_host, "mojplaywin.com")

    def test_partial_save_cannot_hide_status_transition(self):
        self.post()
        lead = SignalInterest.objects.get()
        lead.status = "withdrawn"
        with self.assertRaises(ValidationError):
            lead.save(update_fields=["updated_at"])
        lead.refresh_from_db()
        self.assertEqual(lead.status, "new")
        self.assertIsNone(lead.withdrawn_at)

    def test_withdrawn_lead_remains_withdrawn_on_new_form_and_other_brands_work(self):
        self.post()
        self.post({**self.BASE, "brand": "zahra"})
        lead = SignalInterest.objects.get(brand="saman")
        lead.status = "withdrawn"
        lead.save(update_fields=["status"])
        self.assertEqual(self.post().status_code, 202)
        self.assertEqual(SignalInterest.objects.get(brand="saman").status, "withdrawn")
        other = SignalInterest.objects.get(brand="zahra")
        self.assertEqual(other.status, "new")
        self.assertIsNone(other.withdrawn_at)
        self.assertEqual(SignalInterest.objects.count(), 2)

    def test_owner_admin_displays_withdrawal_receipt_read_only(self):
        a = site._registry[SignalInterest]
        self.assertIn("withdrawn_at", a.list_display)
        self.assertIn("withdrawn_at", a.readonly_fields)
        self.assertIn("withdrawn_at", a.fields)

    def test_owner_counts_enquiries_without_fabricating_revenue(self):
        from core.models import CommercialInterest
        self.post()
        self.post({**self.BASE, "brand": "zahra"})
        first = CommercialInterest.objects.get(brand="saman")
        first.status = "contacted"
        first.save(update_fields=["status"])
        a = site._registry[CommercialInterest]
        user = SimpleNamespace(is_active=True, is_superuser=True, is_staff=True)
        counts = a.lead_counts(SimpleNamespace(user=user))
        self.assertEqual(counts["signals_new"], 1)
        self.assertEqual(counts["signals_contacted"], 1)
        self.assertEqual(counts["signals_withdrawn"], 0)
        self.assertEqual(counts["moj_prop_new"], 0)
        self.assertNotIn("revenue", counts)

    def test_pipeline_metrics_are_not_available_to_nonowner(self):
        a = site._registry[SignalInterest]
        for u in (SimpleNamespace(is_active=True, is_superuser=False),
                  SimpleNamespace(is_active=False, is_superuser=True)):
            self.assertEqual(a.lead_counts(SimpleNamespace(user=u)), {})
