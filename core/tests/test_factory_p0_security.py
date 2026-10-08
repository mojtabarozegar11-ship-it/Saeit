import tempfile
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from django.urls import reverse
from rest_framework.test import APIClient

from core.autonomous_brain import AutonomousBrain
from core.factory_agent_runtime import FactoryAgentBlocked, FactoryAgentRuntime, FixtureResearchProvider
from core.factory_artifact_verifier import ArtifactVerificationError, StaticResearchBriefVerifier
from core.factory_builder import FactoryBuildError, StaticResearchBriefBuilder
from core.factory_contracts import FactoryAgentOutput, GatewayAdapterReceipt
from core.factory_governance import (
    assert_activation_allowed, canonical_spec_digest, snapshot_for, validate_task_prerequisites,
)
from core.factory_tool_pack import build_factory_gateway
from core.models import (
    Agent, AgentTask, AgentToolGrant, ApprovalRequest, FactoryEvidence, FactoryMarketEligibility,
    FactoryRun, Product, ResearchSource,
)
from core.worker_runner import WorkerRunner
from core.task_runtime import TaskRuntime
from core.tool_gateway import ToolGatewayError


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

    def test_gateway_rejects_direct_or_forged_factory_output_without_effect(self):
        task = self.plan_research("p0-forged-output")
        running = TaskRuntime().claim(task.pk)
        gateway = build_factory_gateway()
        gateway.authorize(task.action_type, running.input_data, task_id=running.pk, execution_id=running.execution_id)
        forged = FactoryAgentOutput("product_research", {
            "title": "Forged", "sources": [
                {"url": "https://fake.test/1", "finding": "one"},
                {"url": "https://fake.test/2", "finding": "two"},
            ],
        })
        with self.assertRaises(ToolGatewayError):
            gateway.invoke(
                task.action_type, running.input_data, task_id=running.pk,
                execution_id=running.execution_id, agent_output=forged,
            )
        self.assertFalse(Product.objects.exists())

        fake_receipt = GatewayAdapterReceipt(
            task_id=running.pk, agent_id=running.agent_id, execution_id=running.execution_id,
            action=task.action_type, resource="product:new", environment=running.environment,
            prerequisite_digest=running.prerequisite_snapshot["digest"],
            output_digest="0" * 64, values=forged.values, nonce=object(),
        )
        with self.assertRaises(ToolGatewayError):
            gateway.invoke(
                task.action_type, running.input_data, task_id=running.pk,
                execution_id=running.execution_id, adapter_receipt=fake_receipt,
            )
        self.assertFalse(Product.objects.exists())

    def test_mutated_executor_output_receipt_is_rejected_before_product_creation(self):
        task = self.plan_research("p0-mutated-receipt")
        running = TaskRuntime().claim(task.pk)
        gateway = build_factory_gateway()
        authorization = gateway.authorize(
            task.action_type, running.input_data, task_id=running.pk, execution_id=running.execution_id
        )
        receipt = gateway.execute_factory_adapter(
            FactoryAgentRuntime(research_provider=FixtureResearchProvider()), running, authorization
        )
        receipt.values["title"] = "Changed after validation"
        with self.assertRaisesRegex(ToolGatewayError, "mutated"):
            gateway.invoke(
                task.action_type, running.input_data, task_id=running.pk,
                execution_id=running.execution_id, adapter_receipt=receipt,
            )
        self.assertFalse(Product.objects.exists())

    def test_task_intent_payload_override_is_rejected_at_gateway(self):
        task = self.plan_research("p0-payload-override")
        running = TaskRuntime().claim(task.pk)
        gateway = build_factory_gateway()
        gateway.authorize(task.action_type, running.input_data, task_id=running.pk, execution_id=running.execution_id)
        override = {**running.input_data, "product_id": 999}
        with self.assertRaisesRegex(ToolGatewayError, "persisted Task intent"):
            gateway.invoke(
                task.action_type, override, task_id=running.pk, execution_id=running.execution_id,
                adapter_receipt=GatewayAdapterReceipt(
                    task_id=running.pk, agent_id=running.agent_id, execution_id=running.execution_id,
                    action=task.action_type, resource="product:new", environment=running.environment,
                    prerequisite_digest=running.prerequisite_snapshot["digest"],
                    output_digest="0" * 64, values={}, nonce=object(),
                ),
            )
        self.assertFalse(Product.objects.exists())

    def test_old_authorization_token_fails_after_retry_before_provider(self):
        task = self.plan_research("p0-old-token-retry")
        runtime = TaskRuntime()
        old_execution = runtime.claim(task.pk)
        gateway = build_factory_gateway()
        authorization = gateway.authorize(
            task.action_type, old_execution.input_data, task_id=task.pk, execution_id=old_execution.execution_id
        )
        runtime.fail(task.pk, RuntimeError("retry"), execution_id=old_execution.execution_id)
        retry = runtime.claim(task.pk)
        provider = CountingProvider()
        with self.assertRaises(Exception):
            FactoryAgentRuntime(research_provider=provider).execute(
                retry, authorization=authorization, authorization_check=gateway.is_authorized
            )
        self.assertEqual(provider.calls, 0)
        self.assertFalse(Product.objects.exists())

    def test_old_authorization_token_fails_after_lease_reclaim_before_provider(self):
        task = self.plan_research("p0-old-token-reclaim")
        runtime = TaskRuntime()
        old_execution = runtime.claim(task.pk)
        gateway = build_factory_gateway()
        authorization = gateway.authorize(
            task.action_type, old_execution.input_data, task_id=task.pk, execution_id=old_execution.execution_id
        )
        AgentTask.objects.filter(pk=task.pk).update(updated_at=timezone.now() - timedelta(hours=1))
        runtime.recover_stale(task.pk, stale_after_seconds=1)
        AgentTask.objects.filter(pk=task.pk).update(next_retry_at=timezone.now() - timedelta(seconds=1))
        reclaimed = runtime.claim(task.pk)
        provider = CountingProvider()
        with self.assertRaises(Exception):
            FactoryAgentRuntime(research_provider=provider).execute(
                reclaimed, authorization=authorization, authorization_check=gateway.is_authorized
            )
        self.assertEqual(provider.calls, 0)
        self.assertFalse(Product.objects.exists())

    def test_expired_execution_lease_is_rejected_before_provider(self):
        task = self.plan_research("p0-expired-execution")
        running = TaskRuntime().claim(task.pk)
        gateway = build_factory_gateway()
        authorization = gateway.authorize(
            running.action_type, running.input_data, task_id=running.pk,
            execution_id=running.execution_id,
        )
        AgentTask.objects.filter(pk=task.pk).update(updated_at=timezone.now() - timedelta(hours=1))
        provider = CountingProvider()
        with self.assertRaises(FactoryAgentBlocked):
            FactoryAgentRuntime(research_provider=provider).execute(
                running, authorization=authorization, authorization_check=gateway.is_authorized,
            )
        self.assertEqual(provider.calls, 0)
        self.assertFalse(Product.objects.exists())

    def test_missing_prerequisite_evidence_fails_closed(self):
        product = Product.objects.create(
            title="Missing lineage", product_type="digital",
            metadata={"factory_state": "researched", "research": {"sources": [{}, {}]}},
        )
        run = FactoryRun.objects.create(run_id="p0-missing-lineage", product=product, goal=self.goal)
        agent = Agent.objects.create(code="missing-lineage", name="Missing lineage", mission="Test", active=True)
        task = AgentTask.objects.create(
            agent=agent, action_type="product_opportunity_score", capability_code="product_opportunity_score",
            product=product, factory_run=run, goal=self.goal, prerequisite_snapshot={
                **snapshot_for("product_opportunity_score", product, run)
            },
        )
        with self.assertRaisesRegex(ValidationError, "missing its required predecessor evidence"):
            validate_task_prerequisites(task)

    def test_expired_prerequisite_evidence_fails_closed(self):
        product, run, _ = self.run_factory("p0-expired-evidence", 2)
        score = run.evidence.get(evidence_type="product_opportunity_score")
        score.valid_until = timezone.now() - timedelta(seconds=1)
        score.save(update_fields=["valid_until", "updated_at"])
        task = AutonomousBrain().plan_product_factory_step(
            payload={"goal": self.goal}, product_id=product.pk, run_id=run.run_id
        )
        with self.assertRaisesRegex(ValidationError, "prerequisites are stale"):
            validate_task_prerequisites(task)

    def test_invalid_predecessor_lineage_cannot_be_consumed(self):
        product, run, _ = self.run_factory("p0-invalid-lineage", 2)
        research = run.evidence.get(evidence_type="product_research")
        research.status = FactoryEvidence.INVALID
        research.save(update_fields=["status", "updated_at"])
        task = AutonomousBrain().plan_product_factory_step(
            payload={"goal": self.goal}, product_id=product.pk, run_id=run.run_id
        )
        with self.assertRaisesRegex(ValidationError, "prerequisites are stale"):
            validate_task_prerequisites(task)

    def test_canonical_spec_digest_ignores_claimed_digest_but_tracks_content(self):
        spec = {"version": 2, "problem": "Original", "acceptance_criteria": ["works"], "digest": "claimed"}
        actual = canonical_spec_digest(spec)
        forged = {**spec, "digest": "f" * 64}
        self.assertEqual(actual, canonical_spec_digest(forged))
        changed = {**forged, "problem": "Tampered"}
        self.assertNotEqual(actual, canonical_spec_digest(changed))

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

    def run_factory(self, run_id, steps, include_launch_candidate=False):
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
        for _ in range(min(steps, 11)):
            task = brain.plan_product_factory_step(
                payload={"goal": self.goal}, product_id=product_id, run_id=run_id,
            )
            last = WorkerRunner(build_factory_gateway(), factory_executor=executor).run(task.pk)
            product_id = last.output_data["product_id"]
        if include_launch_candidate or steps > 11:
            # Stage 15 is intentionally outside autonomous planning. Security tests
            # may construct it explicitly to exercise the future owner-gated release boundary.
            product = Product.objects.get(pk=product_id)
            run = FactoryRun.objects.get(run_id=run_id)
            agent = Agent.objects.get(code="factory-launch-candidate-agent")
            task = AgentTask.objects.create(
                agent=agent, action_type="product_launch_candidate",
                capability_code="product_launch_candidate", risk_snapshot="high",
                goal=self.goal, factory_run=run, product=product,
                input_data={"goal": self.goal, "product_id": product.pk, "run_id": run.run_id},
                output_contract={"required": ["launch_candidate"]},
                prerequisite_snapshot=snapshot_for("product_launch_candidate", product, run),
                environment=settings.SAEIT_ENV,
            )
            ApprovalRequest.objects.create(
                action_type="product_launch_candidate", target_type="AgentTask",
                target_id=str(task.pk), reason="Authorize isolated security test",
                risk="high", status="approved", requested_by=self.owner,
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
        self.assertTrue(evidence)
        self.assertTrue(all(item.status == FactoryEvidence.STALE for item in evidence))

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
        product, _, _ = self.run_factory("p0-approval-binding", 11)
        request = ApprovalRequest(
            action_type="delete_product", target_type="Product", target_id=str(product.pk),
            reason="Unrelated approval", risk="high", status="approved", requested_by=self.owner,
        )
        with self.assertRaises(ValidationError):
            request.save()

    def test_spec_or_artifact_change_after_approval_invalidates_release(self):
        product, run, _ = self.run_factory("p0-release-binding", 12)
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

    def test_cached_approval_is_rejected_after_revoke_from_independent_object(self):
        product, _, _ = self.run_factory("p0-cached-approval-revoke", 12)
        product.owner = self.owner
        product.save(update_fields=["owner", "updated_at"])
        approval = ApprovalRequest.objects.create(
            action_type="activate_product", target_type="Product", target_id=str(product.pk),
            reason="Approve exact Factory release", risk="high", requested_by=self.owner,
        )
        approval.status = "approved"
        approval.save(update_fields=["status", "updated_at"])
        cached_gate = product.factory_release_gate
        self.assertEqual(cached_gate.approval.status, "approved")
        separate_approval = ApprovalRequest.objects.get(pk=approval.pk)
        separate_approval.revoked_at = timezone.now()
        separate_approval.save(update_fields=["revoked_at", "updated_at"])
        product.active = True
        with self.assertRaises(ValidationError):
            product.save()
        self.assertFalse(Product.objects.get(pk=product.pk).active)

    def test_expired_market_eligibility_invalidates_approved_manifest(self):
        product, _, _ = self.run_factory("p0-market-expiry", 12)
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
        product, _, _ = self.run_factory("p0-artifact-binding", 12)
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
        product, _, _ = self.run_factory("p0-approval-expiry", 11)
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
