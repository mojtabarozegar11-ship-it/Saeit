"""Production-shaped sales follow-up selection; no messages or payment calls."""
import io
import json
from datetime import timedelta
from decimal import Decimal

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone

from core.management.commands.mojprop_sales_action_queue import action_queue_snapshot
from core.models import MojPropDeliveryEvidence, MojPropOffer, MojPropRequest


class MojPropSalesQueueTests(TestCase):
    def _lead(self, ref, *, status="new", horizon="week", route="brief",
              age_hours=0, product_id=None):
        row = MojPropRequest.objects.create(
            request_id=ref, name="Private buyer", email="buyer-" + ref + "@example.org",
            route=route, status=status, horizon=horizon, product_id=product_id,
            notes="Produce a written educational market briefing with dated sources.",
            consent=True, source="moj-prop-public",
        )
        if age_hours:
            MojPropRequest.objects.filter(pk=row.pk).update(
                created_at=timezone.now() - timedelta(hours=age_hours)
            )
        return row

    def _offer(self, lead, *, status="draft", created_hours=0,
               expires_hours=48, version=1):
        now = timezone.now()
        reviewed_at = now - timedelta(hours=72) if status != "draft" else None
        issued_at = now - timedelta(hours=48) if status in (
            "issued", "accepted", "cancelled", "expired"
        ) else None
        accepted_at = now - timedelta(hours=30) if status == "accepted" else None
        row = MojPropOffer.objects.create(
            lead=lead, version=version, title="Scoped research deliverable",
            scope="A verifiable independent educational report with data and limitations.",
            amount=Decimal("125.00"), currency="USD", delivery_days=5,
            status=status, reviewed_at=reviewed_at, issued_at=issued_at,
            accepted_at=accepted_at,
            expires_at=now + timedelta(hours=expires_hours) if issued_at else None,
            acceptance_reference="verified-manual-customer-consent" if accepted_at else "",
        )
        if created_hours:
            MojPropOffer.objects.filter(pk=row.pk).update(
                created_at=now - timedelta(hours=created_hours)
            )
        return row

    def _delivery(self, offer, *, status):
        now = timezone.now()
        return MojPropDeliveryEvidence.objects.create(
            offer=offer, artifact_sha256="a" * 64, artifact_name="private.pdf",
            status=status,
            clearance_reference="manual-scope-clearance" if status != "prepared" else "",
            handoff_reference="independent-delivery-reference" if status != "prepared" else "",
            handed_off_at=now - timedelta(hours=26) if status != "prepared" else None,
        )

    def categories(self):
        return {item["category"]: item for item in action_queue_snapshot()["categories"]}

    def test_empty_production_snapshot_never_claims_sales(self):
        data = action_queue_snapshot()
        self.assertEqual(data["category_count"], 13)
        self.assertEqual(data["total_queue_entries"], 0)
        self.assertIsNone(data["independent_customer_count"])
        self.assertIsNone(data["collected_revenue"])
        self.assertFalse(data["payment_or_delivery_automatically_approved"])
        self.assertTrue(all(item["count"] == 0 for item in data["categories"]))

    def test_urgent_new_leads_are_actionable_immediately(self):
        self._lead("URGENT", status="new", horizon="urgent", age_hours=2)
        self._lead("NEWER", status="new", horizon="urgent")
        self.assertEqual(self.categories()["urgent_unreviewed"]["count"], 2)

    def test_new_lead_older_than_day_is_escalated(self):
        self._lead("OLDER", age_hours=26)
        self.assertEqual(self.categories()["new_over_24h"]["count"], 1)

    def test_reviewing_lead_with_no_draft_is_actionable(self):
        a = self._lead("REVIEW-1", status="reviewing")
        b = self._lead("REVIEW-2", status="reviewing")
        self._offer(b, status="draft")
        self.assertEqual(self.categories()["reviewing_without_draft"]["count"], 1)

    def test_draft_older_than_day_requires_manual_review(self):
        lead = self._lead("DRAFT")
        self._offer(lead, created_hours=30)
        self.assertEqual(self.categories()["draft_over_24h"]["count"], 1)

    def test_approved_quote_waits_for_owner_before_issuance(self):
        lead = self._lead("APPROVED", status="reviewing")
        self._offer(lead, status="approved")
        self.assertEqual(self.categories()["approved_not_issued"]["count"], 1)

    def test_issued_quote_near_expiry_is_tracked(self):
        lead = self._lead("SOON")
        self._offer(lead, status="issued", expires_hours=12)
        self.assertEqual(self.categories()["issued_expires_soon"]["count"], 1)

    def test_expired_issued_quote_is_not_a_new_revenue_event(self):
        lead = self._lead("EXPIRED")
        self._offer(lead, status="issued", expires_hours=-1)
        self.assertEqual(self.categories()["issued_already_expired"]["count"], 1)
        self.assertEqual(self.categories()["issued_expires_soon"]["count"], 0)

    def test_accepted_offer_without_artifact_needs_delivery_work(self):
        lead = self._lead("ACCEPTED")
        self._offer(lead, status="accepted")
        self.assertEqual(self.categories()["accepted_no_artifact"]["count"], 1)

    def test_prepared_file_is_not_improperly_counted_as_dispatched(self):
        lead = self._lead("PREPARED")
        offer = self._offer(lead, status="accepted")
        self._delivery(offer, status="prepared")
        self.assertEqual(self.categories()["accepted_no_artifact"]["count"], 0)
        self.assertEqual(self.categories()["prepared_not_dispatched"]["count"], 1)

    def test_sent_unacknowledged_after_day_enters_queue(self):
        lead = self._lead("SENT")
        offer = self._offer(lead, status="accepted")
        self._delivery(offer, status="sent")
        self.assertEqual(self.categories()["sent_unacknowledged"]["count"], 1)

    def test_latest_cancelled_offer_is_internal_review_without_outreach(self):
        lead = self._lead("CANCELLED-REVIEW", route="signals", status="reviewing")
        self._offer(lead, status="cancelled", expires_hours=-2)
        entry = self.categories()["terminal_offer_internal_review"]
        self.assertEqual(entry["count"], 1)
        self.assertTrue(entry["operator_only"])
        self.assertFalse(entry["customer_outreach_authorized"])

    def test_latest_expired_offer_is_not_silently_lost(self):
        lead = self._lead("EXPIRED-REVIEW", route="blueprint", status="offer_sent")
        self._offer(lead, status="expired", expires_hours=-3)
        self.assertEqual(self.categories()["terminal_offer_internal_review"]["count"], 1)

    def test_superseding_new_offer_removes_terminal_internal_alert(self):
        lead = self._lead("REVISED-REVIEW", route="signals")
        self._offer(lead, status="cancelled", version=1)
        self._offer(lead, status="approved", version=2)
        self.assertEqual(self.categories()["terminal_offer_internal_review"]["count"], 0)

    def test_only_latest_of_multiple_cancelled_versions_is_counted(self):
        lead = self._lead("REVISED-CANCELLED", route="signals")
        self._offer(lead, status="cancelled", version=1)
        self._offer(lead, status="expired", version=2, expires_hours=-1)
        self.assertEqual(self.categories()["terminal_offer_internal_review"]["count"], 1)

    def test_terminal_internal_review_excludes_optout_and_closed_buyers(self):
        for status in ("closed", "spam", "delivered"):
            lead = self._lead("TERMINAL-"+status, route="signals", status=status)
            self._offer(lead, status="cancelled")
        opted_out = self._lead("OPTED-OUT", route="signals")
        self._offer(opted_out, status="expired")
        MojPropRequest.objects.filter(pk=opted_out.pk).update(consent=False)
        entry = self.categories()["terminal_offer_internal_review"]
        self.assertEqual(entry["count"], 0)

    def test_terminal_internal_details_are_private_and_not_contact_authorization(self):
        lead = self._lead("PRIVATE-TERMINAL", route="signals")
        self._offer(lead, status="cancelled")
        summary = action_queue_snapshot()
        self.assertNotIn(lead.email, str(summary))
        self.assertNotIn("request_refs", str(summary))
        detail = action_queue_snapshot(detail_limit=2)
        section = next(x for x in detail["categories"]
                       if x["category"] == "terminal_offer_internal_review")
        self.assertEqual(section["request_refs"], [lead.request_id])
        self.assertFalse(section["customer_outreach_authorized"])
        self.assertNotIn(lead.email, str(detail))

    def test_digital_and_signal_routes_have_separate_commercial_followups(self):
        self._lead("PRODUCT", route="digital", product_id=72)
        self._lead("SIGNALS", route="signals")
        self.assertEqual(self.categories()["digital_without_issued_quote"]["count"], 1)
        self.assertEqual(self.categories()["signals_without_issued_quote"]["count"], 1)

    def test_spam_and_closed_leads_never_trigger_followup(self):
        self._lead("SPAM", route="signals", status="spam", age_hours=50)
        self._lead("CLOSED", route="signals", status="closed", age_hours=50)
        self.assertEqual(self.categories()["signals_without_issued_quote"]["count"], 0)
        self.assertEqual(self.categories()["new_over_24h"]["count"], 0)

    def test_default_cli_contains_counts_but_no_personal_data_or_ids(self):
        lead = self._lead("PRIVATE-ID", route="signals")
        out = io.StringIO()
        call_command("mojprop_sales_action_queue", stdout=out)
        raw = out.getvalue()
        self.assertNotIn(lead.request_id, raw)
        self.assertNotIn(lead.email, raw)
        self.assertNotIn(lead.name, raw)
        self.assertNotIn("request_refs", raw)
        self.assertEqual(json.loads(raw)["schema"], "mojprop.sales_action_queue.v1")

    def test_explicit_details_only_expose_internal_request_reference(self):
        lead = self._lead("INTERNAL-ONLY", route="signals")
        out = io.StringIO()
        call_command("mojprop_sales_action_queue", details=True, limit=2, stdout=out)
        result = json.loads(out.getvalue())
        self.assertEqual(result["categories"][-1]["request_refs"], [lead.request_id])
        self.assertNotIn(lead.email, out.getvalue())

    def test_detail_limit_is_strictly_bounded(self):
        for invalid in (-1, 26, True, "10"):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                action_queue_snapshot(detail_limit=invalid)
        with self.assertRaises(CommandError):
            call_command("mojprop_sales_action_queue", details=True, limit=30)

    def test_closed_leads_do_not_pollute_human_followup_actions(self):
        for status in ("closed", "spam", "delivered"):
            lead = self._lead("END-" + status, status=status)
            self._offer(lead, status="draft", created_hours=48)
            other = self._lead("END-APPROVED-" + status, status=status)
            self._offer(other, status="approved", created_hours=48)
            # Records exist, but a closed customer is not contactable.
        report = self.categories()
        self.assertEqual(report["draft_over_24h"]["count"], 0)
        self.assertEqual(report["approved_not_issued"]["count"], 0)

    def test_closed_lead_with_expiring_offer_not_recontacted(self):
        for status in ("closed", "spam", "delivered"):
            lead = self._lead("CLOSE-" + status, status=status)
            self._offer(lead, status="issued", expires_hours=6)
        self.assertEqual(self.categories()["issued_expires_soon"]["count"], 0)

    def test_all_queue_categories_reject_unconsented_customer_contacts(self):
        lead = self._lead("NO-CONSENT", status="new", horizon="urgent",
                          route="signals", age_hours=50)
        offer = self._offer(lead, status="accepted")
        self._delivery(offer, status="sent")
        MojPropRequest.objects.filter(pk=lead.pk).update(consent=False)
        report = action_queue_snapshot(detail_limit=10)
        self.assertEqual(report["total_queue_entries"], 0)
        self.assertTrue(all(not entry["request_refs"] for entry in report["categories"]))

    def test_closed_customer_accepted_and_delivery_queues_are_not_outreach(self):
        for state in ("closed", "spam", "delivered"):
            a = self._lead("END-ACCEPT-" + state, status=state)
            self._offer(a, status="accepted")
            b = self._lead("END-PREP-" + state, status=state)
            self._delivery(self._offer(b, status="accepted"), status="prepared")
            c = self._lead("END-SENT-" + state, status=state)
            self._delivery(self._offer(c, status="accepted"), status="sent")
        report = self.categories()
        for category in ("accepted_no_artifact", "prepared_not_dispatched",
                         "sent_unacknowledged"):
            with self.subTest(category=category):
                self.assertEqual(report[category]["count"], 0)
