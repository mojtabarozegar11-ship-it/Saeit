"""Source-backed metrics contract: no invented factory health or earned money."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from core.models import Agent, AgentTask, Order, PaymentIntent, Product


class StaffEvidenceMetricsTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user(
            username="ci_staff", password="local-only", is_staff=True
        )

    def test_anonymous_and_nonstaff_denied(self):
        path=reverse("command_center_evidence_metrics_api")
        self.assertEqual(self.client.get(path).status_code,302)
        other=get_user_model().objects.create_user(username="ci_guest", password="local")
        self.client.force_login(other)
        self.assertEqual(self.client.get(path).status_code,302)

    def test_counts_from_actual_models_without_fake_revenue(self):
        agent=Agent.objects.create(code="metricstest",name="QA",mission="CI only",active=True)
        AgentTask.objects.create(agent=agent,status="completed")
        Product.objects.create(title="QA item",product_type="digital",active=True)
        order=Order.objects.create(customer=self.user,status="paid",total="39.00",currency="USD")
        PaymentIntent.objects.create(
            order=order,amount="39.00",currency="USD",
            idempotency_key="ci-evidence-only",status="paid",provider="test"
        )
        self.client.force_login(self.user)
        response=self.client.get(reverse("command_center_evidence_metrics_api"))
        self.assertEqual(response.status_code,200)
        self.assertIn("no-store",response["Cache-Control"])
        data=response.json()
        self.assertEqual(data["agents"]["registered"],1)
        self.assertEqual(data["agents"]["tasks"]["by_status"]["completed"],1)
        self.assertEqual(data["catalog"]["products"],1)
        self.assertEqual(data["catalog"]["active_products"],1)
        self.assertEqual(data["orders"]["total"],1)
        self.assertEqual(data["payments"]["intents"],1)
        self.assertIsNone(data["payments"]["verified_mainnet_settlements"])
        self.assertIsNone(data["revenue"]["verified_amounts_by_currency"])
        self.assertEqual(data["revenue"]["state"],"unknown")
        self.assertEqual(data["factory"]["state"],"unknown")
        self.assertEqual(data["agents"]["runtime_state"],"unknown")
        self.assertEqual(data["scope"],"shared_core_models_not_proven_exclusive_to_mojplaywin")

    def test_no_mutating_http_methods_and_dashboard_renders(self):
        path=reverse("command_center_evidence_metrics_api")
        self.client.force_login(self.user)
        self.assertEqual(self.client.post(path,data={}).status_code,405)
        page=self.client.get(reverse("command_center_dashboard"))
        self.assertEqual(page.status_code,200)
        self.assertContains(page,"staff-commerce")
        self.assertContains(page,path)
