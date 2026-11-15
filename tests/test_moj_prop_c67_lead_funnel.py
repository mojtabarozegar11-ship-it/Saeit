"""Real Moj Prop CRM reporting; never manufacture buyer payments or leak PII."""
import json
from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone
from core.models import MojPropRequest


class MojPropC67LeadFunnelTests(TestCase):
    def make(self, n, status="new", age_hours=1, route="blueprint"):
        row=MojPropRequest.objects.create(
            request_id=f"MOJPROP-C67-{n}",
            name="Buyer Private", email=f"buyer{n}@example.org",
            route=route, horizon="week",
            notes="Request: price and scope for an education market brief",
            status=status, consent=True, source="moj-prop-public",
        )
        MojPropRequest.objects.filter(pk=row.pk).update(
            created_at=timezone.now()-timedelta(hours=age_hours))
        return row

    def report(self, *args):
        out=StringIO()
        call_command("moj_prop_lead_funnel",*args,stdout=out)
        return out.getvalue()

    def test_zero_real_customers_is_zero_not_a_fabricated_sale(self):
        result=json.loads(self.report("--json"))
        self.assertEqual(result["manual_requests_received"],0)
        self.assertIsNone(result["confirmed_paid_revenue_usd"])

    def test_report_counts_only_existing_canonical_leads(self):
        self.make(1)
        self.make(2,status="reviewing",route="brief")
        report=json.loads(self.report("--json"))
        self.assertEqual(report["manual_requests_received"],2)
        self.assertEqual(report["by_route"]["brief"],1)
        self.assertEqual(report["by_status"]["reviewing"],1)

    def test_overdue_review_metric_only_counts_new_older_than_24h(self):
        self.make(1,age_hours=30)
        self.make(2,age_hours=1)
        self.make(3,status="reviewing",age_hours=48)
        r=json.loads(self.report("--json"))
        self.assertEqual(r["past_24h_review_sla"],1)
        self.assertEqual(r["new_unreviewed"],2)
        self.assertEqual(r["under_review"],1)

    def test_recent_window_omits_old_historical_requests(self):
        self.make(1,age_hours=216)
        self.make(2,age_hours=2)
        self.assertEqual(json.loads(self.report("--days","7","--json"))[
            "manual_requests_received"],1)

    def test_invalid_zero_days_refused(self):
        with self.assertRaisesRegex(CommandError,"days_must"):
            self.report("--days","0")

    def test_invalid_over_90_day_window_refused(self):
        with self.assertRaisesRegex(CommandError,"days_must"):
            self.report("--days","365")

    def test_stdout_contains_no_private_person_fields(self):
        self.make(1)
        for args in [(),("--json",)]:
            output=self.report(*args)
            self.assertNotIn("Buyer Private",output)
            self.assertNotIn("buyer1@example.org",output)
            self.assertNotIn("Request: price",output)

    def test_even_delivered_lead_does_not_claim_tron_payment(self):
        self.make(1,status="delivered")
        r=json.loads(self.report("--json"))
        self.assertEqual(r["by_status"]["delivered"],1)
        self.assertIsNone(r["confirmed_paid_revenue_usd"])
        self.assertFalse(r["settlement_evidence_checked"])

    def test_reporting_does_not_mutate_customer_database(self):
        self.make(1)
        initial=list(MojPropRequest.objects.values_list(
            "request_id","status","updated_at"))
        self.report()
        self.report("--json")
        self.assertEqual(initial,list(MojPropRequest.objects.values_list(
            "request_id","status","updated_at")))

    def test_plain_text_explicitly_marks_revenue_unverified(self):
        self.make(1)
        s=self.report()
        self.assertIn("inquiries=1",s)
        self.assertIn("paid_revenue=NOT_VERIFIED",s)
