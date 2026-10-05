import hashlib
import json
import tempfile
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from io import StringIO
from unittest.mock import patch

from core.autonomous_brain import AutonomousBrain
from core.factory_agent_runtime import FactoryAgentBlocked, FactoryAgentRuntime, FixtureResearchProvider
from core.factory_artifact_verifier import StaticResearchBriefVerifier
from core.factory_builder import StaticResearchBriefBuilder
from core.factory_tool_pack import build_factory_gateway
from core.models import AgentTask, FactoryArtifact, FactoryEvidence, FactoryRun, Product, ResearchSource
from core.task_runtime import TaskRuntime
from core.worker_runner import WorkerRunner


@override_settings(FACTORY_ENVIRONMENT="development")
class FactoryP1RuntimeTests(TestCase):
    def setUp(self):
        call_command("seed_factory_agents", verbosity=0)
        self.owner = get_user_model().objects.create_superuser(
            username="p1-factory-owner", email="p1-owner@example.com", password="test-only"
        )
        self.goal = "Create a small evidence-backed harvest tracking brief."
        self.run_id = "p1-e2e-run"
        self.brain = AutonomousBrain()
        self.tempdir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tempdir.cleanup()

    def test_goal_to_independent_research_score_spec_build_and_test_security(self):
        first = self.brain.plan_product_factory_step(
            payload={"goal": self.goal}, run_id=self.run_id,
        )
        self.assertEqual(first.input_data, {"goal": self.goal, "run_id": self.run_id})
        self.assertNotIn("sources", first.input_data)
        self.assertNotIn("score", first.input_data)
        self.assertNotIn("spec", first.input_data)
        self.assertNotIn("artifact", first.input_data)
        self.assertNotIn("tests", first.input_data)
        self.assertNotIn("security", first.input_data)

        executor = FactoryAgentRuntime(
            research_provider=FixtureResearchProvider(),
            builder=StaticResearchBriefBuilder(self.tempdir.name),
            verifier=StaticResearchBriefVerifier(),
        )
        with patch("core.management.commands.autonomous_master_loop.FactoryAgentRuntime", return_value=executor):
            output = StringIO()
            call_command(
                "autonomous_master_loop", factory=True, goal=self.goal, run_id=self.run_id,
                max_steps=7, stdout=output,
            )
        self.assertIn("FACTORY_PAUSED", output.getvalue())
        self.assertEqual(AgentTask.objects.filter(factory_run__run_id=self.run_id).count(), 7)

        run = FactoryRun.objects.get(run_id=self.run_id)
        product = Product.objects.get(pk=run.product_id)
        evidence = FactoryEvidence.objects.filter(run=run, status=FactoryEvidence.VALID)
        self.assertEqual(evidence.count(), 6)
        research = product.metadata["research"]
        self.assertFalse(research["real_research"])
        self.assertEqual(research["research_provider"], "fixture")
        self.assertEqual(len(research["evidence"]), 2)
        sources = ResearchSource.objects.filter(project_id=research["research_project_id"])
        self.assertEqual(sources.count(), 2)
        for source in sources:
            self.assertTrue(source.retrieved_at)
            self.assertTrue(source.snapshot_hash)
            self.assertEqual(len(source.snapshot_hash), 64)
            self.assertEqual(source.provenance["real_research"], False)

        score = product.metadata["opportunity"]
        self.assertEqual(score["rubric"]["id"], "wealth-opportunity-v1")
        self.assertEqual(score["rubric"]["evidence_ids"], [item["evidence_id"] for item in research["evidence"]])
        self.assertEqual(score["score"], 73.57)
        spec = product.metadata["spec"]
        spec_digest = spec.pop("digest")
        self.assertEqual(spec_digest, hashlib.sha256(
            json.dumps(spec, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest())
        spec["digest"] = spec_digest
        artifact = FactoryArtifact.objects.get(run=run, version=1)
        self.assertEqual(artifact.content_digest, product.metadata["build"]["sha256"])
        self.assertTrue(Path(artifact.reference).is_file())
        tests = product.metadata["test_attestation"]
        security = product.metadata["security_attestation"]
        self.assertTrue(tests["passed"])
        self.assertTrue(security["passed"])
        self.assertEqual(tests["build_digest"], artifact.content_digest)
        self.assertEqual(security["build_digest"], artifact.content_digest)
        self.assertEqual(product.metadata["factory_state"], "security_verified")
        self.assertFalse(product.active)

    @override_settings(FACTORY_RESEARCH_PROVIDER="")
    def test_missing_real_provider_blocks_instead_of_claiming_research_success(self):
        task = self.brain.plan_product_factory_step(
            payload={"goal": self.goal}, run_id=self.run_id,
        )
        with self.assertRaises(FactoryAgentBlocked):
            WorkerRunner(
                build_factory_gateway(), factory_executor=FactoryAgentRuntime()
            ).run(task.pk)
        task.refresh_from_db()
        run = FactoryRun.objects.get(run_id=self.run_id)
        self.assertEqual(task.status, "blocked")
        self.assertNotEqual(task.status, "completed")
        self.assertIsNone(run.product_id)

    def test_owner_can_resume_blocked_work_after_documented_remediation(self):
        task = self.brain.plan_product_factory_step(
            payload={"goal": self.goal}, run_id=self.run_id,
        )
        task.status = "blocked"
        task.save(update_fields=["status", "updated_at"])
        resumed = TaskRuntime().resume_blocked(task.pk, self.owner, "Configured the approved research provider.")
        self.assertEqual(resumed.status, "queued")
        self.assertIsNone(resumed.next_retry_at)

