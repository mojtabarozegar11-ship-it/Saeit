import hashlib
import tempfile
from datetime import timedelta
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from core.autonomous_brain import AutonomousBrain
from core.factory_agent_runtime import (
    FactoryAgentBlocked, FactoryAgentRuntime, FixtureResearchProvider, ResearchProvider,
    research_plan,
)
from core.factory_economics import score_opportunity, validate_opportunity
from core.factory_governance import _assert_real_research_for_release
from core.factory_tool_pack import build_factory_gateway
from core.models import AgentTask, Evidence, FactoryEvidence, FactoryRun, Product, ResearchProject, ResearchSource
from core.task_runtime import TaskRuntime
from core.worker_runner import WorkerRunner


class ProviderFailure(ResearchProvider):
    provider_name = "failing-test-provider"
    real_research = False

    def search(self, **kwargs):
        self.calls = getattr(self, "calls", 0) + 1
        raise RuntimeError("provider timeout")


class PartialEvidenceProvider(ResearchProvider):
    """Non-real deterministic provider used to exercise bounded re-research."""
    provider_name = "partial-test-provider"
    real_research = False
    extractor_version = "test-extractor-v1"

    def __init__(self):
        self.calls = 0

    def search(self, *, goal, constraints, plan, task, authorization, authorization_check,
               timeout_seconds, max_results, max_snapshot_bytes, max_redirects, safe_url_policy):
        if not authorization_check(authorization, task, "product_research"):
            raise FactoryAgentBlocked("authorization lost")
        self.calls += 1
        rows = []
        for number in range(2):
            host = f"research-{self.calls}-{number}.example.test"
            url = f"https://{host}/snapshot"
            if not safe_url_policy(url):
                raise FactoryAgentBlocked("unsafe URL rejected before provider fetch")
            passage = f"Test source {self.calls}-{number}: observed demand for {goal}."
            snapshot = f"Captured source {self.calls}-{number}\n{passage}\n"
            rows.append({
                "title": f"Test source {self.calls}-{number}", "url": url,
                "requested_url": url, "final_url": url, "publisher": f"Test publisher {self.calls}-{number}",
                "query": plan["queries"][0], "provider_request_id": f"test-request-{self.calls}-{number}",
                "retrieved_at": timezone.now().isoformat(), "content_type": "text/plain",
                "snapshot": snapshot, "snapshot_sha256": hashlib.sha256(snapshot.encode()).hexdigest(),
                "passage": passage, "passage_locator": {"line": 2},
                "extractor_version": self.extractor_version, "source_type": "secondary",
                "confidence": "0.8", "economic_factors": {
                    "market_demand": {"value": 70 + self.calls, "claim": passage},
                }, "provenance": {"test_only": True},
            })
        return rows


class DuplicateHostProvider(PartialEvidenceProvider):
    provider_name = "duplicate-host-test-provider"

    def search(self, **kwargs):
        rows = super().search(**kwargs)
        first = rows[0]
        second = dict(first)
        second["title"] = "Second passage from same publisher"
        second["source_identity"] = "spoofed-independent-publisher"
        second["passage"] = "A second passage that cannot create source independence."
        second["snapshot"] = first["snapshot"] + second["passage"]
        second["snapshot_sha256"] = hashlib.sha256(second["snapshot"].encode()).hexdigest()
        second["passage_locator"] = {"line": 3}
        return [first, second]


class PrivateURLProvider(PartialEvidenceProvider):
    def search(self, **kwargs):
        rows = super().search(**kwargs)
        for row in rows:
            row["url"] = row["requested_url"] = row["final_url"] = "http://169.254.169.254/latest/meta-data"
        return rows


class InternalFetchAttemptProvider(ResearchProvider):
    provider_name = "internal-fetch-attempt-provider"
    real_research = False

    def __init__(self):
        self.fetches = 0

    def search(self, **kwargs):
        if not kwargs["safe_url_policy"]("http://169.254.169.254/latest/meta-data"):
            raise FactoryAgentBlocked("unsafe URL rejected before provider fetch")
        self.fetches += 1
        return []


class FactoryPackageCTests(TestCase):
    def setUp(self):
        call_command("seed_factory_agents", verbosity=0)
        self.owner = get_user_model().objects.create_superuser(
            username="package-c-owner", email="package-c-owner@example.com", password="test-only"
        )
        self.goal = "Test whether small farms need a low-cost harvest workflow brief."
        self.run_id = "package-c-main-run"
        self.brain = AutonomousBrain()

    def fixture_records(self):
        provider = FixtureResearchProvider()
        plan = research_plan(self.goal)
        rows = provider.search(
            goal=self.goal, constraints=[], plan=plan, task=object(), authorization=object(),
            authorization_check=lambda *_: True, timeout_seconds=20, max_results=6,
            max_snapshot_bytes=512000, max_redirects=3,
            safe_url_policy=lambda url: url.startswith("fixture://"),
        )
        for index, item in enumerate(rows, 1):
            item["evidence_id"] = index
        return rows

    def executor(self, provider=None):
        return FactoryAgentRuntime(research_provider=provider or FixtureResearchProvider())

    def run_next(self, executor, product_id=None):
        task = self.brain.plan_product_factory_step(
            payload={"goal": self.goal}, product_id=product_id, run_id=self.run_id
        )
        return WorkerRunner(build_factory_gateway(), factory_executor=executor).run(task.pk)

    def test_goal_autonomously_reaches_spec_through_mandatory_validation(self):
        executor = self.executor()
        product_id = None
        actions = []
        for _ in range(4):
            completed = self.run_next(executor, product_id)
            actions.append(completed.action_type)
            product_id = completed.output_data["product_id"]
            self.assertFalse(set(completed.input_data) & {
                "sources", "evidence", "score", "validation", "spec", "artifact", "tests", "security"
            })
        self.assertEqual(actions, [
            "product_research", "product_opportunity_score", "product_validation", "product_spec"
        ])
        product = Product.objects.get(pk=product_id)
        self.assertEqual(product.metadata["validation"]["outcome"], "VALIDATED")
        self.assertEqual(product.metadata["factory_state"], "specified")
        self.assertEqual(product.metadata["spec"]["validation_reference"]["outcome"], "VALIDATED")
        self.assertTrue(product.metadata["spec"]["acceptance_criteria"])
        self.assertEqual(FactoryEvidence.objects.filter(run__run_id=self.run_id, status=FactoryEvidence.VALID).count(), 4)

    def test_fixture_provenance_and_snapshot_hash_are_explicitly_non_real(self):
        completed = self.run_next(self.executor())
        product = Product.objects.get(pk=completed.output_data["product_id"])
        self.assertFalse(product.metadata["research"]["real_research"])
        self.assertEqual(product.metadata["research"]["research_provider"], "fixture")
        project = ResearchProject.objects.get(pk=product.metadata["research"]["research_project_id"])
        source = project.sources.order_by("pk").first()
        provenance = source.provenance
        self.assertFalse(provenance["real_research"])
        self.assertEqual(provenance["run_id"], self.run_id)
        self.assertEqual(provenance["task_id"], completed.pk)
        self.assertEqual(provenance["execution_id"], completed.execution_id)
        self.assertTrue(provenance["provider_request_id"])
        self.assertTrue(provenance["query"])
        self.assertTrue(provenance["requested_url"])
        self.assertTrue(provenance["final_url"])
        self.assertTrue(provenance["content_type"])
        self.assertTrue(provenance["passage_locator"])
        self.assertTrue(provenance["extractor_version"])
        self.assertEqual(
            source.snapshot_hash,
            hashlib.sha256(provenance["snapshot_text"].encode("utf-8")).hexdigest(),
        )
        self.assertNotEqual(source.snapshot_hash, hashlib.sha256(source.evidence.first().passage.encode()).hexdigest())

    def test_provider_failure_creates_no_fabricated_project_or_evidence_and_blocks_run(self):
        task = self.brain.plan_product_factory_step(payload={"goal": self.goal}, run_id=self.run_id)
        provider = ProviderFailure()
        with self.assertRaises(FactoryAgentBlocked):
            WorkerRunner(build_factory_gateway(), factory_executor=self.executor(provider)).run(task.pk)
        task.refresh_from_db()
        run = FactoryRun.objects.get(run_id=self.run_id)
        self.assertEqual(provider.calls, 2)
        self.assertEqual(task.status, "blocked")
        self.assertEqual(run.status, "blocked")
        self.assertIsNone(run.product_id)
        self.assertFalse(ResearchProject.objects.exists())
        self.assertFalse(Evidence.objects.exists())
        self.assertFalse(FactoryEvidence.objects.exists())
        self.assertFalse(Product.objects.exists())

    def test_internal_metadata_endpoint_is_rejected_before_evidence_persistence(self):
        task = self.brain.plan_product_factory_step(payload={"goal": self.goal}, run_id=self.run_id)
        with self.assertRaisesRegex(FactoryAgentBlocked, "unsafe"):
            WorkerRunner(build_factory_gateway(), factory_executor=self.executor(PrivateURLProvider())).run(task.pk)
        self.assertFalse(ResearchProject.objects.exists())
        self.assertFalse(Evidence.objects.exists())

    def test_provider_safe_url_policy_blocks_internal_fetch_before_effect(self):
        provider = InternalFetchAttemptProvider()
        task = self.brain.plan_product_factory_step(payload={"goal": self.goal}, run_id=self.run_id)
        with self.assertRaisesRegex(FactoryAgentBlocked, "before provider fetch"):
            WorkerRunner(build_factory_gateway(), factory_executor=self.executor(provider)).run(task.pk)
        self.assertEqual(provider.fetches, 0)
        self.assertFalse(ResearchProject.objects.exists())

    def test_duplicate_passages_from_same_host_do_not_create_independent_sources(self):
        provider = DuplicateHostProvider()
        completed = self.run_next(self.executor(provider))
        product = Product.objects.get(pk=completed.output_data["product_id"])
        research = product.metadata["research"]
        self.assertEqual(len(research["evidence"]), 1)
        project = ResearchProject.objects.get(pk=research["research_project_id"])
        self.assertEqual(project.sources.count(), 1)
        self.assertEqual(research["evidence"][0]["source_identity"], "research-1-0.example.test")

    def test_scoring_is_versioned_reproducible_and_references_exact_evidence_digests(self):
        rows = self.fixture_records()
        one = score_opportunity(rows)
        two = score_opportunity(rows)
        self.assertEqual(one, two)
        self.assertEqual(one["rubric"]["version"], "wealth-opportunity-v1")
        self.assertEqual(one["rubric"]["evidence_ids"], [1, 2])
        factor_ref = one["rubric"]["inputs"]["market_demand"]["evidence"][0]
        self.assertEqual(factor_ref["evidence_id"], 1)
        self.assertEqual(factor_ref["snapshot_digest"], rows[0]["snapshot_hash"])
        self.assertEqual(one["rubric"]["evidence_digest"], score_opportunity(rows)["rubric"]["evidence_digest"])

    def test_unknown_economic_inputs_remain_unknown_and_validation_requests_evidence(self):
        rows = [
            {"source_identity": "a.example.test", "evidence_id": 1, "snapshot_hash": "a" * 64, "economic_factors": {}},
            {"source_identity": "b.example.test", "evidence_id": 2, "snapshot_hash": "b" * 64, "economic_factors": {}},
        ]
        score = score_opportunity(rows)
        self.assertIsNone(score["score"])
        self.assertTrue(all(value["status"] == "UNKNOWN / NEEDS_EVIDENCE" and value["value"] is None
                            for value in score["rubric"]["inputs"].values()))
        decision = validate_opportunity(score, rows, research_attempts=1)
        self.assertEqual(decision["outcome"], "NEEDS_MORE_EVIDENCE")
        self.assertIn("market_demand", decision["missing_factors"])

    def test_validation_can_validate_reject_request_research_again_and_block(self):
        rows = self.fixture_records()
        score = score_opportunity(rows)
        self.assertEqual(validate_opportunity(score, rows, 1)["outcome"], "VALIDATED")
        weak = {**score, "score": 20}
        self.assertEqual(validate_opportunity(weak, rows, 1)["outcome"], "REJECTED")
        partial = score_opportunity(rows[:1])
        self.assertEqual(validate_opportunity(partial, rows[:1], 1)["outcome"], "NEEDS_MORE_EVIDENCE")
        self.assertEqual(validate_opportunity(partial, rows[:1], 2)["outcome"], "BLOCKED")
        conflict_rubric = {**score["rubric"], "conflicts": ["market_demand"]}
        conflict = {**score, "rubric": conflict_rubric}
        self.assertEqual(validate_opportunity(conflict, rows, 1)["outcome"], "RESEARCH_AGAIN")

    def test_master_bounded_reresearch_and_validation_block_are_durable(self):
        provider = PartialEvidenceProvider()
        executor = self.executor(provider)
        product_id = None
        actions = []
        for _ in range(6):
            completed = self.run_next(executor, product_id)
            actions.append(completed.action_type)
            product_id = completed.output_data["product_id"]
        run = FactoryRun.objects.get(run_id=self.run_id)
        product = Product.objects.get(pk=product_id)
        self.assertEqual(actions, [
            "product_research", "product_opportunity_score", "product_validation",
            "product_research", "product_opportunity_score", "product_validation",
        ])
        self.assertEqual(provider.calls, 2)
        self.assertEqual(product.metadata["validation"]["outcome"], "BLOCKED")
        self.assertEqual(product.metadata["factory_state"], "blocked")
        self.assertEqual(run.status, "blocked")
        self.assertEqual(self.brain.decide_product_factory_step(product.pk, run.run_id)["action"], "blocked")
        with self.assertRaises(RuntimeError):
            self.brain.plan_product_factory_step(payload={"goal": self.goal}, product_id=product.pk, run_id=run.run_id)

    def test_spec_runtime_refuses_to_create_before_valid_validation(self):
        run = FactoryRun.objects.create(run_id="package-c-no-validation", goal=self.goal)
        product = Product.objects.create(
            title="Unvalidated", product_type="digital",
            metadata={"factory_state": "scored", "research": {"evidence": [{"evidence_id": 1, "snapshot_hash": "a" * 64}]}},
        )
        run.product = product
        run.save(update_fields=["product", "updated_at"])
        task = SimpleNamespace(factory_run_id=True, factory_run=run, goal=self.goal)
        with self.assertRaises(FactoryAgentBlocked):
            self.executor()._spec(task, product)
        self.assertNotIn("spec", product.metadata)

    def test_fixture_evidence_is_rejected_at_production_release_boundary(self):
        product_id = None
        executor = self.executor()
        for _ in range(8):
            completed = self.run_next(executor, product_id)
            product_id = completed.output_data["product_id"]
        product = Product.objects.get(pk=product_id)
        with self.assertRaisesRegex(ValidationError, "Fixture/non-real"):
            _assert_real_research_for_release(product)
