import tempfile
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from core.autonomous_brain import AutonomousBrain
from core.factory_agent_runtime import FactoryAgentRuntime, FixtureResearchProvider
from core.factory_builder import StaticResearchBriefBuilder
from core.factory_governance import invalidate_stale_evidence
from core.factory_tool_pack import build_factory_gateway
from core.models import AgentTask, FactoryEvidence, FactoryMarketEligibility, FactoryRun, Product
from core.worker_runner import WorkerRunner


class FactoryPackageDTests(TestCase):
    def setUp(self):
        call_command("seed_factory_agents", verbosity=0)
        self.owner = get_user_model().objects.create_superuser(
            username="package-d-owner", email="package-d@example.com", password="test-only"
        )
        self.market = FactoryMarketEligibility.objects.create(
            market_code="US", eligibility=FactoryMarketEligibility.ALLOWED,
            evidence_reference="https://example.com/owner-market-review",
            review_note="Owner-reviewed deterministic Gate-80 fixture.",
            reviewed_by=self.owner, reviewed_at=timezone.now(),
            valid_until=timezone.now() + timedelta(days=30),
        )
        self.goal = "Produce a source-backed harvest workflow brief."
        self.run_id = "package-d-acceptance"
        self.brain = AutonomousBrain()
        self.workspace = tempfile.TemporaryDirectory()
        self.addCleanup(self.workspace.cleanup)
        self.executor = FactoryAgentRuntime(
            research_provider=FixtureResearchProvider(),
            builder=StaticResearchBriefBuilder(self.workspace.name),
        )

    def run_next(self, product_id=None):
        task = self.brain.plan_product_factory_step(
            payload={"goal": self.goal}, product_id=product_id, run_id=self.run_id
        )
        return WorkerRunner(build_factory_gateway(), factory_executor=self.executor).run(task.pk)

    def specified_product(self):
        product_id = None
        for _ in range(4):
            done = self.run_next(product_id)
            product_id = done.output_data["product_id"]
        product = Product.objects.get(pk=product_id)
        self.assertEqual(product.metadata["factory_state"], "specified")
        return product

    def test_validated_spec_autonomously_reaches_inactive_launch_candidate_with_exact_lineage(self):
        product = self.specified_product()
        # Package-D acceptance starts here: the only input is the already persisted,
        # independently verified Product Spec. The factory creates every later artifact.
        start_task_count = AgentTask.objects.filter(factory_run__run_id=self.run_id).count()
        actions = []
        for _ in range(7):
            done = self.run_next(product.pk)
            actions.append(done.action_type)
            product.refresh_from_db()
        self.assertEqual(actions, [
            "product_build_record", "product_test", "product_security", "product_localize",
            "product_market_eligibility", "product_qa", "product_launch_candidate",
        ])
        self.assertEqual(
            AgentTask.objects.filter(factory_run__run_id=self.run_id).count() - start_task_count, 7
        )
        meta = product.metadata
        build = meta["build"]
        self.assertEqual(build["spec_digest"], meta["spec"]["digest"])
        self.assertEqual(meta["test_attestation"]["build_digest"], build["sha256"])
        self.assertEqual(meta["security_attestation"]["build_digest"], build["sha256"])
        self.assertEqual(meta["localization"]["build_digest"], build["sha256"])
        self.assertEqual(meta["qa_attestation"]["build_digest"], build["sha256"])
        candidate = meta["launch_candidate"]
        self.assertEqual(candidate["spec_digest"], meta["spec"]["digest"])
        self.assertEqual(candidate["build_digest"], build["sha256"])
        self.assertEqual(candidate["test_attestation_digest"], meta["test_attestation"]["attestation_digest"])
        self.assertEqual(candidate["security_attestation_digest"], meta["security_attestation"]["attestation_digest"])
        self.assertEqual(candidate["qa_attestation_digest"], meta["qa_attestation"]["attestation_digest"])
        self.assertFalse(candidate["published"])
        self.assertFalse(candidate["deployed"])
        self.assertFalse(product.active)
        self.assertEqual(meta["factory_state"], "launch_candidate")
        agents = dict(AgentTask.objects.filter(factory_run__run_id=self.run_id).values_list("action_type", "agent__code"))
        self.assertNotEqual(agents["product_build_record"], agents["product_test"])
        self.assertNotEqual(agents["product_build_record"], agents["product_security"])
        self.assertNotEqual(agents["product_build_record"], agents["product_qa"])

    def test_expired_market_blocks_before_qa_and_launch(self):
        product = self.specified_product()
        for _ in range(4):
            done = self.run_next(product.pk)
            product.refresh_from_db()
        self.market.valid_until = timezone.now() - timedelta(seconds=1)
        self.market.save()
        task = self.brain.plan_product_factory_step(
            payload={"goal": self.goal}, product_id=product.pk, run_id=self.run_id
        )
        with self.assertRaises(Exception):
            WorkerRunner(build_factory_gateway(), factory_executor=self.executor).run(task.pk)
        product.refresh_from_db()
        self.assertNotIn(product.metadata["factory_state"], {"eligible", "qa_passed", "launch_candidate"})

    def test_upstream_spec_change_stales_downstream_evidence(self):
        product = self.specified_product()
        for _ in range(3):
            self.run_next(product.pk)
            product.refresh_from_db()
        run = FactoryRun.objects.get(run_id=self.run_id)
        self.assertTrue(run.evidence.filter(evidence_type="product_security", status=FactoryEvidence.VALID).exists())
        spec = dict(product.metadata["spec"])
        spec["problem"] = spec["problem"] + " changed"
        product.metadata = {**product.metadata, "spec": spec}
        product.save(update_fields=["metadata", "updated_at"])
        invalidate_stale_evidence(product)
        self.assertTrue(run.evidence.filter(
            evidence_type__in=["product_build_record", "product_test", "product_security"],
            status=FactoryEvidence.STALE,
        ).exists())
