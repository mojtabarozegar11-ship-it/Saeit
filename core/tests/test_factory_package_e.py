import tempfile
from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.utils import timezone

from core.factory_agent_runtime import FactoryAgentBlocked, FactoryAgentRuntime, FixtureResearchProvider, ResearchProvider
from core.factory_artifact_verifier import StaticResearchBriefVerifier
from core.factory_builder import StaticResearchBriefBuilder
from core.factory_governance import _assert_real_research_for_release, invalidate_stale_evidence
from core.models import AgentTask, AuditLog, FactoryEvidence, FactoryMarketEligibility, FactoryRun, Product


class OneShotTestFailureVerifier(StaticResearchBriefVerifier):
    def __init__(self):
        self.calls = 0

    def test(self, *args, **kwargs):
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("deterministic recoverable tester outage")
        return super().test(*args, **kwargs)


class PolicyBlockedProvider(ResearchProvider):
    provider_name = "policy-blocked-ci-provider"
    real_research = False

    def search(self, **kwargs):
        raise FactoryAgentBlocked("deterministic policy block")


@override_settings(FACTORY_RETRY_BACKOFF_SECONDS=0)
class FactoryPackageEGoalOnlyTests(TestCase):
    def setUp(self):
        call_command("seed_factory_agents", verbosity=0)
        self.owner = get_user_model().objects.create_superuser(
            username="package-e-owner", email="package-e@example.com", password="test-only"
        )
        FactoryMarketEligibility.objects.create(
            market_code="US", eligibility=FactoryMarketEligibility.ALLOWED,
            evidence_reference="https://example.com/package-e-owner-review",
            review_note="Pre-existing owner-governed deterministic CI market eligibility.",
            reviewed_by=self.owner, reviewed_at=timezone.now(),
            valid_until=timezone.now() + timedelta(days=30),
        )
        self.goal = "Create an evidence-backed harvest workflow brief from one owner goal."
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def executor(self, verifier=None, provider=None):
        return FactoryAgentRuntime(
            research_provider=provider or FixtureResearchProvider(),
            builder=StaticResearchBriefBuilder(self.tmp.name),
            verifier=verifier or StaticResearchBriefVerifier(),
        )

    def run_goal_only(self, run_id, executor=None, max_steps=20, include_goal=True):
        output = StringIO()
        args = {"factory": True, "run_id": run_id, "max_steps": max_steps, "stdout": output}
        if include_goal:
            args["goal"] = self.goal
        with patch("core.management.commands.autonomous_master_loop.FactoryAgentRuntime",
                   return_value=executor or self.executor()):
            call_command("autonomous_master_loop", **args)
        return output.getvalue()

    def test_goal_only_happy_path_creates_every_stage_and_launch_candidate(self):
        run_id = "package-e-goal-only"
        output = self.run_goal_only(run_id)
        self.assertIn("FACTORY_LAUNCH_CANDIDATE", output)
        run = FactoryRun.objects.get(run_id=run_id)
        product = Product.objects.get(pk=run.product_id)
        tasks = list(run.tasks.order_by("created_at", "pk"))
        expected = [
            "product_research", "product_opportunity_score", "product_validation", "product_spec",
            "product_build_record", "product_test", "product_security", "product_localize",
            "product_market_eligibility", "product_qa", "product_launch_candidate",
        ]
        self.assertEqual([task.action_type for task in tasks], expected)
        self.assertTrue(all(task.goal == self.goal for task in tasks))
        forbidden = {"sources", "evidence", "score", "validation", "spec", "artifact",
                     "tests", "security", "localization", "markets", "qa", "launch_candidate"}
        self.assertTrue(all(not (set(task.input_data) & forbidden) for task in tasks))
        self.assertEqual(
            AuditLog.objects.filter(action="factory_next_step_planned", target_id__in=[str(x.pk) for x in tasks]).count(),
            len(expected),
        )
        self.assertEqual(run.goal, self.goal)
        self.assertEqual(product.metadata["factory_state"], "launch_candidate")
        candidate = product.metadata["launch_candidate"]
        self.assertEqual(candidate["spec_digest"], product.metadata["spec"]["digest"])
        self.assertEqual(candidate["build_digest"], product.metadata["build"]["sha256"])
        self.assertEqual(candidate["test_attestation_digest"], product.metadata["test_attestation"]["attestation_digest"])
        self.assertEqual(candidate["security_attestation_digest"], product.metadata["security_attestation"]["attestation_digest"])
        self.assertEqual(candidate["qa_attestation_digest"], product.metadata["qa_attestation"]["attestation_digest"])
        self.assertTrue(all(e.prerequisite_digest for e in run.evidence.filter(status=FactoryEvidence.VALID)))
        agents = {task.action_type: task.agent.code for task in tasks}
        self.assertNotEqual(agents["product_build_record"], agents["product_test"])
        self.assertNotEqual(agents["product_build_record"], agents["product_security"])
        self.assertNotEqual(agents["product_build_record"], agents["product_qa"])
        self.assertNotEqual(agents["product_validation"], agents["product_build_record"])
        self.assertFalse(candidate["published"])
        self.assertFalse(candidate["deployed"])
        self.assertFalse(product.active)
        with self.assertRaisesRegex(ValidationError, "Fixture/non-real"):
            _assert_real_research_for_release(product)
        before = run.tasks.count()
        again = self.run_goal_only(run_id, include_goal=False)
        self.assertIn("FACTORY_REPLAN_BLOCKED", again)
        self.assertEqual(run.tasks.count(), before)

    def test_recoverable_worker_failure_retries_same_task_without_human_intervention(self):
        run_id = "package-e-recoverable"
        verifier = OneShotTestFailureVerifier()
        output = self.run_goal_only(run_id, executor=self.executor(verifier=verifier), max_steps=20)
        self.assertIn("FACTORY_RETRY", output)
        self.assertIn("FACTORY_LAUNCH_CANDIDATE", output)
        run = FactoryRun.objects.get(run_id=run_id)
        test_tasks = run.tasks.filter(action_type="product_test")
        self.assertEqual(test_tasks.count(), 1)
        task = test_tasks.get()
        self.assertEqual(task.status, "completed")
        self.assertEqual(task.attempt_count, 2)
        self.assertEqual(verifier.calls, 2)
        self.assertEqual(run.tasks.filter(action_type="product_build_record").count(), 1)
        self.assertEqual(run.tasks.filter(action_type="product_launch_candidate").count(), 1)

    def test_restart_resumes_same_run_without_recreating_goal(self):
        run_id = "package-e-restart"
        first = self.run_goal_only(run_id, max_steps=5)
        self.assertIn("FACTORY_PAUSED", first)
        run = FactoryRun.objects.get(run_id=run_id)
        original_pk, original_goal = run.pk, run.goal
        second = self.run_goal_only(run_id, max_steps=20, include_goal=False)
        self.assertIn("FACTORY_LAUNCH_CANDIDATE", second)
        run.refresh_from_db()
        self.assertEqual(run.pk, original_pk)
        self.assertEqual(run.goal, original_goal)
        self.assertEqual(run.tasks.count(), 11)

    def test_nonrecoverable_policy_failure_is_durably_blocked(self):
        run_id = "package-e-policy-block"
        output = self.run_goal_only(run_id, executor=self.executor(provider=PolicyBlockedProvider()))
        self.assertIn("FACTORY_BLOCKED", output)
        run = FactoryRun.objects.get(run_id=run_id)
        task = run.tasks.get(action_type="product_research")
        self.assertEqual(task.status, "blocked")
        self.assertEqual(run.status, "blocked")
        self.assertEqual(task.attempt_count, 1)
        self.assertFalse(Product.objects.exists())

    def test_upstream_mutation_invalidates_goal_only_downstream_chain(self):
        run_id = "package-e-stale"
        self.run_goal_only(run_id)
        run = FactoryRun.objects.get(run_id=run_id)
        product = Product.objects.get(pk=run.product_id)
        spec = dict(product.metadata["spec"])
        spec["problem"] += " changed upstream"
        product.metadata = {**product.metadata, "spec": spec}
        product.save(update_fields=["metadata", "updated_at"])
        invalidate_stale_evidence(product)
        stale = set(run.evidence.filter(status=FactoryEvidence.STALE).values_list("evidence_type", flat=True))
        self.assertTrue({"product_build_record", "product_test", "product_security", "product_qa",
                         "product_launch_candidate"}.issubset(stale))
