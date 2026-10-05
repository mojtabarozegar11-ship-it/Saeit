import tempfile
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from django.urls import reverse
from rest_framework.test import APIClient

from core.autonomous_brain import AutonomousBrain
from core.factory_agent_runtime import FactoryAgentRuntime, FixtureResearchProvider
from core.factory_artifact_verifier import ArtifactVerificationError, StaticResearchBriefVerifier
from core.factory_builder import FactoryBuildError, StaticResearchBriefBuilder
from core.factory_contracts import FactoryAgentOutput
from core.factory_governance import assert_activation_allowed
from core.factory_tool_pack import build_factory_gateway
from core.models import (
    AgentToolGrant, ApprovalRequest, FactoryEvidence, FactoryMarketEligibility,
    FactoryRun, Product, ResearchSource,
)
from core.worker_runner import WorkerRunner


class CountingProvider(FixtureResearchProvider):
    calls = 0

    def search(self, **kwargs):
        self.calls += 1
        return super().search(**kwargs)


class FactoryP0SecurityTests(TestCase):
    def setUp(self):
        call_command("seed_factory_agents", verbosity=0)
        self.owner = get_user_model().objects.create_superuser(
            username="factory-p0-owner", email="factory-p0@example.com", password="test-only"
        )
        self.goal = "Build an evidence-backed harvest tracking brief."

    def plan_research(self, run_id):
        return AutonomousBrain().plan_product_factory_step(
            payload={"goal": self.goal}, run_id=run_id
        )

    def test_provider_is_never_called_without_effective_grant(self):
        task = self.plan_research("p0-no-grant")
        grant = AgentToolGrant.objects.get(agent=task.agent, capability_code=task.capability_code)
        grant.revoked_at = timezone.now()
        grant.save(update_fields=["revoked_at", "updated_at"])
        provider = CountingProvider()
        with self.assertRaises(Exception):
            WorkerRunner(
                build_factory_gateway(),
                factory_executor=FactoryAgentRuntime(research_provider=provider),
            ).run(task.pk)
        self.assertEqual(provider.calls, 0)
        self.assertEqual(Product.objects.filter(factory_runs__run_id="p0-no-grant").count(), 0)

    def test_expired_grant_fails_closed_before_provider(self):
        task = self.plan_research("p0-expired-grant")
        AgentToolGrant.objects.filter(agent=task.agent).update(
            valid_until=timezone.now() - timedelta(seconds=1)
        )
        provider = CountingProvider()
        with self.assertRaises(Exception):
            WorkerRunner(
                build_factory_gateway(),
                factory_executor=FactoryAgentRuntime(research_provider=provider),
            ).run(task.pk)
        self.assertEqual(provider.calls, 0)

    def test_resource_mismatched_grant_fails_closed_before_provider(self):
        task = self.plan_research("p0-resource-grant")
        AgentToolGrant.objects.filter(agent=task.agent).update(resource_scope="unrelated:*")
        provider = CountingProvider()
        with self.assertRaises(Exception):
            WorkerRunner(
                build_factory_gateway(),
                factory_executor=FactoryAgentRuntime(research_provider=provider),
            ).run(task.pk)
        self.assertEqual(provider.calls, 0)

    def test_invalid_task_output_injection_is_rejected_before_provider(self):
        task = self.plan_research("p0-output-injection")
        task.input_data = {**task.input_data, "sources": [{"url": "https://evil.test", "finding": "fake"}]}
        task.save(update_fields=["input_data", "updated_at"])
        provider = CountingProvider()
        with self.assertRaises(Exception):
            WorkerRunner(
                build_factory_gateway(),
                factory_executor=FactoryAgentRuntime(research_provider=provider),
            ).run(task.pk)
        self.assertEqual(provider.calls, 0)
        self.assertEqual(Product.objects.count(), 0)

    def test_planner_rejects_output_fields_in_task_intent(self):
        before = FactoryRun.objects.count()
        with self.assertRaises(RuntimeError):
            AutonomousBrain().plan_product_factory_step(
                payload={"goal": self.goal, "score": 99}, run_id="p0-intent-injection"
            )
        self.assertEqual(FactoryRun.objects.count(), before)

    def test_typed_output_rejects_agent_attempt_to_override_task_result(self):
        with self.assertRaises(ValueError):
            FactoryAgentOutput.validate(
                "product_research",
                {"title": "injected", "sources": [], "product_id": 999, "verified_effect": True},
            )

    def test_builder_does_not_create_workspace_without_gateway_authorization(self):
        with tempfile.TemporaryDirectory() as parent:
            workspace = Path(parent) / "factory-workspace"
            with self.assertRaises(FactoryBuildError):
                StaticResearchBriefBuilder(workspace).build(
                    run_id="unauthorized", product_id=1, version=1,
                    spec={"acceptance_criteria": []}, evidence=[], task=object(),
                    authorization=None, authorization_check=lambda *_: False,
                )
            self.assertFalse(workspace.exists())

    def test_verifier_refuses_to_run_without_gateway_authorization(self):
        with self.assertRaises(ArtifactVerificationError):
            StaticResearchBriefVerifier().verify(
                object(), {}, task=object(), authorization=None,
                authorization_check=lambda *_: False,
            )

    def run_factory(self, run_id, steps):
        FactoryMarketEligibility.objects.update_or_create(
            market_code="US",
            defaults={
                "eligibility": FactoryMarketEligibility.ALLOWED,
                "evidence_reference": "https://example.com/review",
                "review_note": "Current test review.",
                "reviewed_by": self.owner, "reviewed_at": timezone.now(),
                "valid_until": timezone.now() + timedelta(days=20),
            },
        )
        brain = AutonomousBrain()
        executor = FactoryAgentRuntime(
            research_provider=FixtureResearchProvider(),
            builder=StaticResearchBriefBuilder(tempfile.mkdtemp()),
        )
        product_id = None
        last = None
        for _ in range(steps):
            task = brain.plan_product_factory_step(
                payload={"goal": self.goal}, product_id=product_id, run_id=run_id,
            )
            last = WorkerRunner(build_factory_gateway(), factory_executor=executor).run(task.pk)
            product_id = last.output_data["product_id"]
        return Product.objects.get(pk=product_id), FactoryRun.objects.get(run_id=run_id), last

    def test_research_change_invalidates_all_downstream_and_blocks_stale_consumption(self):
        product, run, _ = self.run_factory("p0-lineage", 5)
        source = ResearchSource.objects.filter(project_id=product.metadata["research"]["research_project_id"]).first()
        source.snapshot_hash = "f" * 64
        source.save(update_fields=["snapshot_hash", "updated_at"])
        evidence = list(run.evidence.order_by("evidence_type"))
        research_evidence = next(item for item in evidence if item.evidence_type == "product_research")
        self.assertEqual(research_evidence.status, FactoryEvidence.VALID)
        downstream = [item for item in evidence if item.evidence_type != "product_research"]
        self.assertTrue(downstream)
        self.assertTrue(all(item.status == FactoryEvidence.STALE for item in downstream))

        next_task = AutonomousBrain().plan_product_factory_step(
            payload={"goal": self.goal}, product_id=product.pk, run_id=run.run_id,
        )
        with self.assertRaises(Exception):
            WorkerRunner(
                build_factory_gateway(),
                factory_executor=FactoryAgentRuntime(research_provider=FixtureResearchProvider()),
            ).run(next_task.pk)

    def test_factory_identity_survives_metadata_removal(self):
        product = Product.objects.create(
            title="Factory identity", product_type="digital",
            metadata={"factory_state": "launch_candidate"},
        )
        product.metadata = {}
        product.save(update_fields=["metadata", "updated_at"])
        product.refresh_from_db()
        self.assertTrue(product.is_factory_managed)
        with self.assertRaises(ValidationError):
            assert_activation_allowed(product)
        with self.assertRaises(ValidationError):
            Product.objects.filter(pk=product.pk).update(factory_managed=False)

    def test_product_api_cannot_activate_around_release_gate(self):
        product = Product.objects.create(
            title="API bypass", product_type="digital", owner=self.owner,
            metadata={"factory_state":"launch_candidate"},
        )
        client = APIClient()
        client.force_authenticate(self.owner)
        response = client.patch(
            reverse("product-detail", args=[product.pk]), {"active": True}, format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Product.objects.get(pk=product.pk).active)

    def test_product_admin_cannot_activate_around_release_gate(self):
        product = Product.objects.create(
            title="Admin bypass", product_type="digital", owner=self.owner,
            metadata={"factory_state": "launch_candidate"},
        )
        self.client.force_login(self.owner)
        with self.assertRaises(ValidationError):
            self.client.post(
                reverse("admin:core_product_change", args=[product.pk]),
                {
                    "title": product.title, "product_type": product.product_type,
                    "price": str(product.price), "currency": product.currency,
                    "active": "on", "owner": str(self.owner.pk),
                    "knowledge_article": "", "metadata": '{"factory_state":"launch_candidate"}',
                    "_save": "Save",
                },
            )
        product.refresh_from_db()
        self.assertFalse(product.active)

    def test_unrelated_or_unbound_approval_cannot_approve_factory_product(self):
        product, _, _ = self.run_factory("p0-approval-binding", 7)
        request = ApprovalRequest(
            action_type="delete_product", target_type="Product", target_id=str(product.pk),
            reason="Unrelated approval", risk="high", status="approved", requested_by=self.owner,
        )
        with self.assertRaises(ValidationError):
            request.save()

    def test_spec_or_artifact_change_after_approval_invalidates_release(self):
        product, run, _ = self.run_factory("p0-release-binding", 7)
        product.owner = self.owner
        product.save(update_fields=["owner", "updated_at"])
        approval = ApprovalRequest.objects.create(
            action_type="activate_product", target_type="Product", target_id=str(product.pk),
            reason="Approve exact Factory release", risk="high", requested_by=self.owner,
        )
        self.assertTrue(approval.release_manifest_digest)
        with self.assertRaises(ValidationError):
            ApprovalRequest.objects.filter(pk=approval.pk).update(status="approved")
        with self.assertRaises(ValidationError):
            product.factory_release_gate.__class__.objects.filter(
                pk=product.factory_release_gate.pk
            ).update(status="approved")
        approval.status = "approved"
        approval.save(update_fields=["status", "updated_at"])
        gate = product.factory_release_gate
        self.assertEqual(gate.manifest.manifest_digest, approval.release_manifest_digest)

        product.metadata = {**product.metadata, "spec": {**product.metadata["spec"], "problem": "changed"}}
        product.save(update_fields=["metadata", "updated_at"])
        product.active = True
        with self.assertRaises(ValidationError):
            product.save()

    def test_expired_market_eligibility_invalidates_approved_manifest(self):
        product, _, _ = self.run_factory("p0-market-expiry", 7)
        product.owner = self.owner
        product.save(update_fields=["owner", "updated_at"])
        approval = ApprovalRequest.objects.create(
            action_type="activate_product", target_type="Product", target_id=str(product.pk),
            reason="Approve exact Factory release", risk="high", requested_by=self.owner,
        )
        approval.status = "approved"
        approval.save(update_fields=["status", "updated_at"])
        market = FactoryMarketEligibility.objects.get(market_code="US")
        market.valid_until = timezone.now() - timedelta(seconds=1)
        market.save(update_fields=["valid_until", "updated_at"])
        candidate = product.factory_release_gate.run.evidence.get(evidence_type="product_launch_candidate")
        candidate.refresh_from_db()
        self.assertEqual(candidate.status, FactoryEvidence.STALE)
        product.active = True
        with self.assertRaises(ValidationError):
            product.save()

    def test_artifact_digest_change_after_approval_rejects_old_manifest(self):
        product, _, _ = self.run_factory("p0-artifact-binding", 7)
        product.owner = self.owner
        product.save(update_fields=["owner", "updated_at"])
        approval = ApprovalRequest.objects.create(
            action_type="activate_product", target_type="Product", target_id=str(product.pk),
            reason="Approve exact Factory release", risk="high", requested_by=self.owner,
        )
        approval.status = "approved"
        approval.save(update_fields=["status", "updated_at"])
        artifact = product.factory_release_gate.artifact
        Path(artifact.reference).chmod(0o644)
        Path(artifact.reference).write_text("changed after approval", encoding="utf-8")
        product.active = True
        with self.assertRaises(ValidationError):
            product.save()

    def test_expired_approval_cannot_activate_current_release(self):
        product, _, _ = self.run_factory("p0-approval-expiry", 7)
        product.owner = self.owner
        product.save(update_fields=["owner", "updated_at"])
        approval = ApprovalRequest.objects.create(
            action_type="activate_product", target_type="Product", target_id=str(product.pk),
            reason="Approve exact Factory release", risk="high", requested_by=self.owner,
        )
        approval.status = "approved"
        approval.save(update_fields=["status", "updated_at"])
        product.active = True
        with patch("core.factory_governance.timezone.now", return_value=approval.expires_at + timedelta(seconds=1)):
            with self.assertRaises(ValidationError):
                product.save()
