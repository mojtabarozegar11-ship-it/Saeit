"""Independent commercial release evidence is mandatory; no live payments."""
import json

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from core.commercialization_readiness import (
    SECTORS, PRIORITY, assess_sector, build_board,
)
from core.models import (
    Product, Order, PaymentIntent, LedgerEntry,
    PaymentWebhookEvent, CommerceFunnelEvent,
)
from core.mojplaywin_product_detail import PUBLIC_CATALOG


class PureCommercializationBoardTests(SimpleTestCase):
    def test_all_twelve_business_lines_exist(self):
        self.assertEqual(len(SECTORS), 12)
        self.assertEqual(set(SECTORS), set(PRIORITY))

    def test_owner_four_priorities_are_immutable(self):
        self.assertEqual(
            PRIORITY[:4],
            ("moj_prop", "signal_subscriptions", "tron_gateway", "mojplaywin_store"),
        )
        self.assertEqual(len(SECTORS["signal_subscriptions"]), 7)
        self.assertEqual(len(SECTORS["tron_gateway"]), 8)
        self.assertEqual(len(SECTORS["mojplaywin_store"]), 7)
        self.assertEqual(sum(len(v) for v in SECTORS.values()), 70)

    def test_moj_coin_is_exact_fifth_priority_not_generic_games(self):
        self.assertEqual(PRIORITY[:5], (
            "moj_prop", "signal_subscriptions", "tron_gateway",
            "mojplaywin_store", "moj_coin",
        ))
        self.assertIn("games", PRIORITY[5:])
        self.assertEqual(len(SECTORS["moj_coin"]), 6)
        self.assertIn("tron_purchase_and_entitlement_reconciled", SECTORS["moj_coin"])
        self.assertIn("token_mechanics_and_local_law_reviewed", SECTORS["moj_coin"])
        self.assertEqual(assess_sector("moj_coin").percent_evidenced, 0)

    def test_all_lines_are_blocked_without_evidence(self):
        result = build_board()
        self.assertEqual(result["eligible_for_commercial_review"], 0)
        self.assertFalse(result["ready_for_live_payment"])
        for line in result["sectors"]:
            self.assertEqual(line["outcome"], "not_released")
            self.assertEqual(line["percent_evidenced"], 0)
            self.assertEqual(line["complete"], 0)
            self.assertEqual(len(line["missing"]), line["required"])

    def test_dict_of_sector_attestations_required(self):
        for invalid in ("yes", True, 1, ["ready"]):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                build_board(invalid)

    def test_one_verified_gate_not_enough(self):
        x = assess_sector("digital_books", {"content_final": True})
        self.assertEqual(x.completed, 1)
        self.assertEqual(x.outcome, "not_released")

    def test_truthy_flags_cannot_forge_attestation(self):
        for value in (1, "true", "yes", [], object()):
            with self.subTest(value=repr(value)):
                x = assess_sector("digital_books", {"content_final": value})
                self.assertEqual(x.completed, 0)

    def test_unknown_business_line_rejected(self):
        with self.assertRaises(ValueError):
            assess_sector("fake_cash")

    def test_invalid_sector_attestation_rejected(self):
        with self.assertRaises(ValueError):
            assess_sector("moj_prop", "all ready")

    def test_all_gates_are_only_eligible_for_review(self):
        for name, gates in SECTORS.items():
            with self.subTest(name=name):
                a = assess_sector(name, {g: True for g in gates})
                self.assertEqual(a.outcome, "eligible_for_commercial_review")
                self.assertEqual(a.percent_evidenced, 100)
                self.assertEqual(a.missing, ())
        result = build_board({n: {g: True for g in gs} for n, gs in SECTORS.items()})
        self.assertFalse(result["ready_for_live_payment"])
        self.assertEqual(result["eligible_for_commercial_review"], 12)

    def test_out_of_scope_flags_do_not_override_missing_required_fields(self):
        a = assess_sector("moj_prop", {"is_admin": True, "automatic_payment": True})
        self.assertEqual(a.completed, 0)

    def test_moj_prop_requires_legal_and_real_broker_gates(self):
        required = SECTORS["moj_prop"]
        self.assertIn("jurisdiction_legal_approval", required)
        self.assertIn("broker_contract_verified", required)
        self.assertIn("funding_and_reserves_attested", required)
        self.assertIn("payout_and_trx_controls_live", required)

    def test_banned_instagram_profile_in_result(self):
        a = build_board()
        self.assertTrue(a["never_auto_post_social"])
        self.assertEqual(a["excluded_instagram_profile"], "Dr.mojtaba.rozegar")

    def test_no_fabricated_verified_income(self):
        self.assertIsNone(build_board()["verified_income_usd"])

    def test_gate_counts_are_exact(self):
        a = assess_sector("website_kits", {
            "artifact_complete": True, "license_reviewed": True,
        })
        self.assertEqual(a.completed, 2)
        self.assertEqual(a.required, 5)
        self.assertEqual(a.percent_evidenced, 40)

    def test_one_missing_gate_blocks_review(self):
        x = {g: True for g in SECTORS["digital_books"]}
        x.pop("recovery_verified")
        a = assess_sector("digital_books", x)
        self.assertEqual(a.outcome, "not_released")
        self.assertEqual(a.missing, ("recovery_verified",))


class CommercializationBoardApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        U = get_user_model()
        cls.staff = U.objects.create_user(
            username="commstaff", password="staff-test-password-only", is_staff=True
        )
        cls.visitor = U.objects.create_user(
            username="commuser", password="user-test-password-only"
        )

    def endpoint(self):
        return reverse("command_center_commercialization_api")

    def test_anonymous_denied(self):
        response = self.client.get(self.endpoint())
        self.assertNotEqual(response.status_code, 200)

    def test_nonstaff_denied(self):
        self.client.force_login(self.visitor)
        response = self.client.get(self.endpoint())
        self.assertNotEqual(response.status_code, 200)

    def test_staff_can_inspect_without_mutating(self):
        self.client.force_login(self.staff)
        response = self.client.get(self.endpoint())
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["ready_for_live_payment"])

    def test_staff_can_distinguish_plan_one_owner_status_from_funded_proof(self):
        self.client.force_login(self.staff)
        body = self.client.get(self.endpoint()).json()
        prop = body["financial_commerce"]["moj_prop"]
        self.assertEqual(prop["plan_products_configured"], 10)
        self.assertEqual(prop["owner_declared_active_plans"], 1)
        self.assertEqual(prop["owner_declared_funded_plans"], 1)
        self.assertEqual(prop["temporary_funding_hold_plans"], 9)
        self.assertEqual(prop["independently_verified_funded_plans_in_catalog"], 0)
        self.assertEqual(prop["plan_statuses"][0]["code"], "MOJ-PROP-01")
        self.assertTrue(prop["plan_statuses"][0]["owner_funding_attested"])
        self.assertFalse(prop["plan_statuses"][0]["checkout_enabled"])
        self.assertTrue(all(plan["temporarily_inactive"] for plan in
                            prop["plan_statuses"][1:]))
        self.assertFalse(prop["live_challenge_checkout_verified"])
        self.assertFalse(prop["real_broker_funding_verified"])
        self.assertFalse(body["ready_for_live_payment"])

    def test_post_never_mutates(self):
        self.client.force_login(self.staff)
        response = self.client.post(self.endpoint(), {"enable_payment": "true"})
        self.assertEqual(response.status_code, 405)

    def test_no_customer_pii(self):
        self.client.force_login(self.staff)
        response = self.client.get(self.endpoint())
        raw = json.dumps(response.json())
        self.assertNotIn("commstaff", raw)
        self.assertNotIn("commuser", raw)
        self.assertNotIn("wallet_address", raw)
        self.assertNotIn("invoice_reference", raw)

    def test_paid_flag_is_counted_but_never_misreported_as_settled_trx_revenue(self):
        Order.objects.create(
            customer=self.visitor, status="paid", total="12.50", currency="USD",
        )
        self.client.force_login(self.staff)
        data = self.client.get(self.endpoint()).json()
        records = data["observed"]["shared_database"]
        self.assertEqual(records["orders_with_paid_status_not_chain_proof"], 1)
        self.assertFalse(records["settled_trx_revenue_independently_verified"])
        self.assertIsNone(data["verified_income_usd"])
        self.assertFalse(data["ready_for_live_payment"])

    def test_no_store_or_payment_rows_created_by_read(self):
        self.client.force_login(self.staff)
        before = (Product.objects.count(), Order.objects.count(),
                  PaymentIntent.objects.count(), LedgerEntry.objects.count())
        for _ in range(2):
            self.client.get(self.endpoint())
        after = (Product.objects.count(), Order.objects.count(),
                 PaymentIntent.objects.count(), LedgerEntry.objects.count())
        self.assertEqual(before, after)

    def test_secure_private_response_headers(self):
        self.client.force_login(self.staff)
        response = self.client.get(self.endpoint())
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(response["X-Robots-Tag"], "noindex, nofollow")
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")

    def test_catalog_only_counts_genuine_active_titles(self):
        Product.objects.create(
            pk=72, title=PUBLIC_CATALOG[72]["title"], active=True,
            product_type="book", price="7.50", currency="USD"
        )
        Product.objects.create(
            pk=225, title="Unrelated content", active=True,
            product_type="book", price="4.00", currency="USD"
        )
        Product.objects.create(
            pk=879, title=PUBLIC_CATALOG[879]["title"], active=False,
            product_type="kit", price="6.80", currency="USD"
        )
        self.client.force_login(self.staff)
        obs = self.client.get(self.endpoint()).json()["observed"]
        self.assertEqual(obs["catalog_products_active_title_matched"], 1)
        self.assertEqual(obs["catalog_matched_ids"], [72])

    def test_shared_db_order_count_not_claimed_as_paid(self):
        order = Order.objects.create(customer=self.visitor, status="paid", total="1.00", currency="USD")
        PaymentIntent.objects.create(
            order=order, amount="1.00", currency="USD", provider="provider_one",
            idempotency_key="financial-intent-not-revenue", status="settled",
        )
        self.client.force_login(self.staff)
        result = self.client.get(self.endpoint()).json()
        self.assertEqual(result["observed"]["shared_database"]["orders_all_brands"], 1)
        self.assertEqual(result["observed"]["shared_database"]["provider_selected_intents_all_brands"], 1)
        self.assertIsNone(result["verified_income_usd"])
        self.assertFalse(result["ready_for_live_payment"])

    def test_local_ledger_entry_is_not_external_settlement(self):
        order = Order.objects.create(customer=self.visitor, total="1.00", currency="USD")
        LedgerEntry.objects.create(
            order=order, entry_type="credit", amount="1.00",
            currency="USD", reference="unverified-fixture-ledger"
        )
        self.client.force_login(self.staff)
        data = self.client.get(self.endpoint()).json()
        self.assertEqual(data["observed"]["shared_database"]["internal_ledger_entries_all_brands"], 1)
        self.assertIsNone(data["verified_income_usd"])

    def test_webhook_received_is_not_successful_payout(self):
        PaymentWebhookEvent.objects.create(
            provider="unknown", event_id="webhook_1",
            event_type="payment", payload_hash="none"
        )
        self.client.force_login(self.staff)
        data = self.client.get(self.endpoint()).json()
        self.assertEqual(data["observed"]["shared_database"]["webhook_events_all_brands"], 1)
        self.assertFalse(data["ready_for_live_payment"])

    def test_funnel_events_are_aggregate_not_sales(self):
        CommerceFunnelEvent.objects.create(event_name="payment_confirmed")
        CommerceFunnelEvent.objects.create(event_name="view_item")
        self.client.force_login(self.staff)
        body = self.client.get(self.endpoint()).json()
        events = body["observed"]["funnel_events_last_30_days_all_brands"]
        self.assertEqual(events["payment_confirmed"], 1)
        self.assertEqual(events["view_item"], 1)
        self.assertIsNone(body["verified_income_usd"])

    def test_route_is_inside_private_staff_area(self):
        self.assertEqual(self.endpoint(), "/staff/command-center/api/commercialization/")

    def test_external_trx_runtime_is_not_claimed_to_be_local_models(self):
        self.client.force_login(self.staff)
        obs = self.client.get(self.endpoint()).json()["observed"]
        self.assertEqual(obs["source"], "shared_django_models_not_external_trx_settlement")

    def test_private_html_page_denied_to_anonymous_visitors(self):
        response = self.client.get(reverse("command_center_commercialization_page"))
        self.assertNotEqual(response.status_code, 200)

    def test_private_html_page_denied_to_nonstaff(self):
        self.client.force_login(self.visitor)
        response = self.client.get(reverse("command_center_commercialization_page"))
        self.assertNotEqual(response.status_code, 200)

    def test_private_html_page_lists_eleven_lines_without_enable_button(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("command_center_commercialization_page"))
        self.assertEqual(response.status_code, 200)
        for key in PRIORITY:
            self.assertContains(response, key)
        self.assertContains(response, "Dr.mojtaba.rozegar")
        html = response.content.decode("utf-8").lower()
        self.assertNotIn("<form", html)
        self.assertNotIn("payment_intent=", html)
        self.assertEqual(response["X-Robots-Tag"], "noindex, nofollow")

    def test_signal_and_tron_priority_metrics_are_evidence_limited(self):
        self.client.force_login(self.staff)
        response = self.client.get(self.endpoint())
        self.assertEqual(response.status_code, 200)
        payload = response.json()["financial_commerce"]
        prop = payload["moj_prop"]
        self.assertEqual(prop["plan_products_configured"], 10)
        self.assertEqual(prop["additional_plan_prices_proposed_not_live"], 9)
        self.assertEqual(prop["plan_one_owner_fee_trx"], "30")
        self.assertEqual(prop["valid_closed_trades_required"], 50)
        self.assertEqual(prop["duration_days"], 28)
        self.assertFalse(prop["live_challenge_checkout_verified"])
        self.assertFalse(prop["real_broker_funding_verified"])
        self.assertEqual(payload["owner_priority_order"][:4], [
            "moj_prop", "signal_subscriptions", "tron_gateway", "mojplaywin_store",
        ])
        self.assertEqual(payload["signals"]["known_financial_brands"], 17)
        self.assertEqual(payload["signals"]["localization_contexts"], 51)
        self.assertEqual(payload["signals"]["live_subscriptions_verified"], 0)
        self.assertEqual(payload["signals"]["canonical_bot"], "mojtaba.bot.ai")
        self.assertEqual(payload["tron"]["grounded_site_domains"], 2)
        self.assertEqual(payload["tron"]["isolated_logical_scopes"], 37)
        self.assertFalse(payload["tron"]["invoice_created_by_this_api"])
        self.assertFalse(payload["tron"]["live_gateway_verified_by_this_api"])

    def test_first_four_commercial_cards_match_owner_order(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("command_center_commercialization_page"))
        self.assertEqual(response.status_code, 200)
        codes = [x["code"] for x in response.context["sectors"]]
        self.assertEqual(codes[:4], [
            "moj_prop", "signal_subscriptions", "tron_gateway", "mojplaywin_store",
        ])
        self.assertContains(response, "۱۲ بخش")

    def test_price_mismatched_catalog_is_excluded_from_price_verified_count(self):
        Product.objects.create(
            pk=72, title=PUBLIC_CATALOG[72]["title"], active=True,
            product_type="book", currency="USD", price="8.00",
        )
        self.client.force_login(self.staff)
        observed = self.client.get(self.endpoint()).json()["observed"]
        self.assertEqual(observed["catalog_products_active_title_matched"], 1)
        self.assertEqual(observed["catalog_products_active_price_matched"], 0)
        self.assertEqual(observed["catalog_price_verified_listing_ids"], [])

    def test_exact_currency_and_price_are_required_for_commercial_listing(self):
        Product.objects.create(
            pk=72, title=PUBLIC_CATALOG[72]["title"], active=True,
            product_type="book", currency="USD", price="7.50",
        )
        Product.objects.create(
            pk=225, title=PUBLIC_CATALOG[225]["title"], active=True,
            product_type="book", currency="EUR", price="4.00",
        )
        self.client.force_login(self.staff)
        observed = self.client.get(self.endpoint()).json()["observed"]
        self.assertEqual(observed["catalog_products_active_title_matched"], 2)
        self.assertEqual(observed["catalog_products_active_price_matched"], 1)
        self.assertEqual(observed["catalog_price_verified_listing_ids"], [72])
