import json
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.utils import timezone
from datetime import timedelta
from io import StringIO
from core.factory_tool_pack import product_research, opportunity_score, product_spec, product_build_record, product_qa, product_localize, launch_candidate
from core.models import Product, FactoryMarketEligibility, FactoryRun, FactoryEvidence, AgentToolGrant
from core.models import Agent, AgentCapability, AgentTask, AuditLog
from core.tool_gateway import ToolGateway, ToolSpec
from core.worker_runner import WorkerRunner
from core.autonomous_brain import AutonomousBrain
from core.factory_governance import snapshot_for

class FactoryToolPackTests(TestCase):
    def test_chain_reaches_launch_candidate_with_evidence(self):
        r=product_research({"title":"Evidence Product","sources":[{"url":"https://example.com/a","finding":"demand"},{"url":"https://example.com/b","finding":"competition"}]})
        pid=r["product_id"]
        opportunity_score({"product_id":pid,"score":82,"rationale":"evidence"})
        product_spec({"product_id":pid,"spec":{"problem":"costly manual work","acceptance_criteria":["saves time"]}})
        product_build_record({"product_id":pid,"artifact":{"ref":"git:abc123"}})
        product_qa({"product_id":pid,"tests":{"passed":True},"security":{"passed":True}})
        product_localize({"product_id":pid,"locales":["en","fa"]})

    def test_invalid_research_is_rejected(self):
        with self.assertRaises(ValueError):
            product_research({"title":"No evidence","sources":[]})

    def test_brain_does_not_trust_direct_or_unverified_metadata_changes(self):
        result = product_research({
            "title":"Unverified product",
            "sources":[{"url":"https://example.com/a","finding":"a"},{"url":"https://example.com/b","finding":"b"}],
        })
        decision = AutonomousBrain().decide_product_factory_step(result["product_id"])
        self.assertEqual(decision["action"], "blocked")
        self.assertIn("completed, verified AgentTask", decision["reason"])

    def test_launch_requires_allowed_market(self):
        r=product_research({"title":"P","sources":[{"url":"https://example.com/a","finding":"a"},{"url":"https://example.com/b","finding":"b"}]})
        pid=r["product_id"]
        opportunity_score({"product_id":pid,"score":70})
        product_spec({"product_id":pid,"spec":{"problem":"p","acceptance_criteria":["a"]}})
        product_build_record({"product_id":pid,"artifact":{"ref":"git:x"}})
        product_qa({"product_id":pid,"tests":{"passed":True},"security":{"passed":True}})
        product_localize({"product_id":pid,"locales":["en"]})
        with self.assertRaises(ValueError):
            launch_candidate({"product_id":pid,"markets":[{"country":"XX","eligibility":"allowed"}]})
        owner = get_user_model().objects.create_superuser(
            username="factory-owner", email="owner@example.com", password="test-only"
        )
        FactoryMarketEligibility.objects.create(
            market_code="US", eligibility=FactoryMarketEligibility.ALLOWED,
            evidence_reference="https://example.com/market-review", reviewed_by=owner,
            review_note="Reviewed for sandbox product test.", reviewed_at=timezone.now(),
            valid_until=timezone.now() + timedelta(days=30),
        )
        out=launch_candidate({"product_id":pid,"markets":[{"country":"US","eligibility":"restricted"}]})
        self.assertEqual(out["factory_state"],"launch_candidate")
        self.assertFalse(Product.objects.get(pk=pid).active)

    def test_agent_cannot_claim_market_allowed_or_reuse_stale_review(self):
        product = Product.objects.create(
            title="Market proof", product_type="digital",
            metadata={"factory_state":"localized", "localization":{"launch_locales":["en"]}},
        )
        owner = get_user_model().objects.create_superuser(
            username="market-owner", email="market-owner@example.com", password="test-only"
        )
        FactoryMarketEligibility.objects.create(
            market_code="GB", eligibility=FactoryMarketEligibility.PENDING_REVIEW,
            review_note="Pending evidence review.", reviewed_by=owner, reviewed_at=timezone.now(),
        )
        with self.assertRaisesRegex(ValueError, "allowed launch market"):
            launch_candidate({"product_id":product.pk,"markets":[{"market_code":"GB","eligibility":"allowed"}]})
        FactoryMarketEligibility.objects.filter(market_code="GB").update(
            eligibility=FactoryMarketEligibility.ALLOWED, review_note="Reviewed but expired.",
            evidence_reference="https://example.com/expired-review", valid_until=timezone.now() - timedelta(seconds=1)
        )
        with self.assertRaisesRegex(ValueError, "review is stale"):
            launch_candidate({"product_id":product.pk,"markets":[{"market_code":"GB","eligibility":"allowed"}]})

    def test_worker_retry_rolls_back_factory_effect_before_replay(self):
        agent = Agent.objects.create(code="factory-retry", name="Factory retry", mission="Research", active=True)
        capability = AgentCapability.objects.create(code="product_research", name="Research", active=True)
        capability.agents.add(agent)
        run = FactoryRun.objects.create(run_id="retry-run", goal="Research a retry-safe product.")
        task = AgentTask.objects.create(
            agent=agent, action_type="product_research", capability_code=capability.code,
            risk_snapshot="low", goal=run.goal, factory_run=run,
            input_data={"goal":run.goal, "run_id":run.run_id},
            output_contract={"required":["title","sources"]},
            prerequisite_snapshot=snapshot_for("product_research", None, run),
        )
        AgentToolGrant.objects.create(agent=agent, capability_code=capability.code,
            tool_code=capability.code, resource_scope="product:*", environment="development")

        def fail_after_effect(payload):
            product_research(payload)
            raise RuntimeError("simulated process failure after database effect")

        with self.assertRaisesRegex(RuntimeError, "simulated process failure"):
            WorkerRunner(ToolGateway([ToolSpec(code="product_research", handler=fail_after_effect)])).run(task.pk, agent_output={
                "title":"Retry-safe product", "sources":[
                    {"url":"https://example.com/a", "finding":"demand"},
                    {"url":"https://example.com/b", "finding":"competition"},
                ]})
        task.refresh_from_db()
        self.assertEqual(task.status, "queued")
        self.assertEqual(Product.objects.filter(title="Retry-safe product").count(), 0)

        completed = WorkerRunner(ToolGateway([ToolSpec(code="product_research", handler=product_research)])).run(task.pk, agent_output={
            "title":"Retry-safe product", "sources":[
                {"url":"https://example.com/a", "finding":"demand"},
                {"url":"https://example.com/b", "finding":"competition"},
            ]})
        self.assertEqual(completed.status, "completed")
        self.assertEqual(Product.objects.filter(title="Retry-safe product").count(), 1)

    def test_master_brain_plans_and_verifies_factory_research_task(self):
        Product.objects.create(title="Existing catalog item", product_type="digital", metadata={})
        agent = Agent.objects.create(
            code="factory-master-agent", name="Factory Master", mission="Coordinate product factory", active=True
        )
        capability = AgentCapability.objects.create(
            code="product_research", name="Market research", risk_level="low", active=True
        )
        capability.agents.add(agent)
        AgentToolGrant.objects.create(agent=agent, capability_code=capability.code,
            tool_code=capability.code, resource_scope="product:*", environment="development")
        brain = AutonomousBrain()

        task = brain.plan_product_factory_step(payload={"goal":"Research a simple harvest workflow for small farms."})
        self.assertEqual(set(task.input_data), {"goal", "run_id"})
        self.assertEqual(task.goal, task.input_data["goal"])
        self.assertEqual(task.action_type, "product_research")
        self.assertEqual(task.status, "queued")
        self.assertTrue(AuditLog.objects.filter(action="factory_next_step_planned", target_id=str(task.pk)).exists())
        self.assertEqual(brain.plan_product_factory_step({"goal":"ignored retry"}).pk, task.pk)

        output = StringIO()
        call_command("factory_product_step", task_id=task.pk, result_json=json.dumps({
            "title":"Farm workflow evidence digest",
            "sources":[
                {"url":"https://example.com/demand", "finding":"Small farms need a simple harvest log."},
                {"url":"https://example.com/alternatives", "finding":"Available tools are overly complex for a small operation."},
            ],
        }), stdout=output)
        completed = AgentTask.objects.get(pk=task.pk)
        self.assertEqual(completed.status, "completed")
        self.assertIn("verified=True", output.getvalue())
        product = Product.objects.get(pk=completed.output_data["product_id"])
        self.assertEqual(product.metadata["factory_state"], "researched")
        self.assertEqual(product.metadata["factory_history"][-1]["task_id"], task.pk)
        next_step = brain.decide_product_factory_step(product.pk)
        self.assertEqual(next_step["action"], "product_opportunity_score")

    def test_master_routes_complete_lifecycle_through_specialists_and_runtime(self):
        call_command("seed_factory_agents", stdout=StringIO())
        owner = get_user_model().objects.create_superuser(
            username="e2e-factory-owner", email="e2e-owner@example.com", password="test-only"
        )
        FactoryMarketEligibility.objects.create(
            market_code="US", eligibility=FactoryMarketEligibility.ALLOWED,
            evidence_reference="https://example.com/market-review", review_note="Test fixture review.",
            reviewed_by=owner, reviewed_at=timezone.now(), valid_until=timezone.now() + timedelta(days=30),
        )
        payloads = [
            {"title":"Farm harvest log", "sources":[
                {"url":"https://example.com/demand", "finding":"Small farms need harvest records."},
                {"url":"https://example.com/competition", "finding":"Current tools are too complex."},
            ]},
            {"score":82, "rationale":"Evidence supports a narrow, low-risk utility."},
            {"spec":{"problem":"Manual harvest records are fragmented.", "acceptance_criteria":["Records a harvest entry.", "Exports a daily summary."]}},
            {"artifact":{"ref":"test-artifact:sha256:fixture-v1"}},
            {"tests":{"passed":True, "run_id":"fixture-tests-1"}, "security":{"passed":True, "run_id":"fixture-security-1"}},
            {"locales":["en", "fa"]},
            {"markets":[{"market_code":"US"}]},
        ]
        brain = AutonomousBrain()
        product_id = None
        task_ids = []
        for payload in payloads:
            task = brain.plan_product_factory_step(payload={"goal":"Build a source-backed farm harvest digital product."}, product_id=product_id)
            self.assertEqual(task.status, "queued")
            task_ids.append(task.pk)
            output = StringIO()
            call_command("factory_product_step", task_id=task.pk, result_json=json.dumps(payload), stdout=output)
            task.refresh_from_db()
            self.assertEqual(task.status, "completed", output.getvalue())
            product_id = task.output_data["product_id"]

        product = Product.objects.get(pk=product_id)
        self.assertEqual(
            [entry["state"] for entry in product.metadata["factory_history"]],
            ["researched", "scored", "specified", "built", "qa_passed", "localized", "launch_candidate"],
        )
        self.assertEqual(list(AgentTask.objects.filter(pk__in=task_ids).order_by("created_at", "pk").values_list("action_type", flat=True)), [
            "product_research", "product_opportunity_score", "product_spec", "product_build_record",
            "product_qa", "product_localize", "product_launch_candidate",
        ])
        self.assertFalse(product.active)
        self.assertEqual(brain.decide_product_factory_step(product.pk)["action"], "owner_approval_boundary")
        self.assertEqual(AuditLog.objects.filter(action="factory_next_step_planned").count(), len(payloads))

    def test_factory_product_activation_is_blocked_without_release_gate_owner_approval(self):
        product = Product.objects.create(
            title="Unreleased", product_type="digital",
            metadata={"factory_state":"launch_candidate"},
        )
        product.active = True
        with self.assertRaisesRegex(Exception, "shared owner Release Gate"):
            product.save()
        with self.assertRaisesRegex(Exception, "shared owner Release Gate"):
            Product.objects.filter(pk=product.pk).update(active=True)

    def test_prerequisite_and_artifact_changes_stale_dependent_evidence(self):
        agent = Agent.objects.create(code="stale-evidence-agent", name="Verifier", mission="Verify")
        product = Product.objects.create(
            title="Versioned product", product_type="digital",
            metadata={"factory_state":"researched", "research":{"sources":[{"url":"a","finding":"one"},{"url":"b","finding":"two"}]}},
        )
        run = FactoryRun.objects.create(run_id="stale-run", product=product, goal="Verify versioned build.", current_artifact_version=1)
        task = AgentTask.objects.create(
            agent=agent, action_type="product_opportunity_score", capability_code="product_opportunity_score",
            goal=run.goal, product=product, factory_run=run,
        )
        snapshot = snapshot_for("product_opportunity_score", product, run)
        evidence = FactoryEvidence.objects.create(
            task=task, run=run, product=product, evidence_type="product_opportunity_score",
            prerequisite_digest=snapshot["digest"], spec_version=run.current_spec_version,
            artifact_version=run.current_artifact_version, details={},
        )
        product.metadata = {**product.metadata, "research":{"sources":[{"url":"a","finding":"changed"},{"url":"b","finding":"two"}]}}
        product.save(update_fields=["metadata", "updated_at"])
        evidence.refresh_from_db()
        self.assertEqual(evidence.status, FactoryEvidence.STALE)

    def test_runtime_rejects_success_claim_without_persisted_product_effect(self):
        agent = Agent.objects.create(code="factory-noop-agent", name="Factory no-op", mission="Score", active=True)
        capability = AgentCapability.objects.create(code="product_opportunity_score", name="Score", active=True)
        capability.agents.add(agent)
        product = Product.objects.create(
            title="No-op product", product_type="digital",
            metadata={"factory_state":"researched", "research":{"sources":[{}, {}]}},
        )
        run = FactoryRun.objects.create(run_id="noop-run", product=product, goal="Score the persisted product.")
        task = AgentTask.objects.create(
            agent=agent, action_type=capability.code, capability_code=capability.code,
            input_data={"goal":run.goal, "product_id":product.pk, "run_id":run.run_id},
            goal=run.goal, product=product, factory_run=run, risk_snapshot="low",
            output_contract={"required":["score"]},
        )
        AgentToolGrant.objects.create(agent=agent, capability_code=capability.code,
            tool_code=capability.code, resource_scope="product:*", environment="development")
        gateway = ToolGateway([ToolSpec(
            code=capability.code,
            handler=lambda payload: {"verified_effect":True,"product_id":product.pk,"factory_state":"scored","score":99},
        )])
        with self.assertRaisesRegex(Exception, "Persisted Product lifecycle state"):
            WorkerRunner(gateway).run(task.pk)
        task.refresh_from_db()
        product.refresh_from_db()
        self.assertEqual(product.metadata["factory_state"], "researched")
        self.assertNotIn("factory_history", product.metadata)
        self.assertEqual(task.status, "queued")
