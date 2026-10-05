from django.test import TestCase
from core.factory_tool_pack import product_research, opportunity_score, product_spec, product_build_record, product_qa, product_localize, launch_candidate
from core.models import Product
from core.models import Agent, AgentCapability, AgentTask, AuditLog
from core.tool_gateway import ToolGateway, ToolSpec
from core.worker_runner import WorkerRunner
from core.autonomous_brain import AutonomousBrain
from core.factory_tool_pack import build_factory_gateway

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

    def test_launch_requires_allowed_market(self):
        r=product_research({"title":"P","sources":[{"url":"https://example.com/a","finding":"a"},{"url":"https://example.com/b","finding":"b"}]})
        pid=r["product_id"]
        opportunity_score({"product_id":pid,"score":70})
        product_spec({"product_id":pid,"spec":{"problem":"p","acceptance_criteria":["a"]}})
        product_build_record({"product_id":pid,"artifact":{"ref":"git:x"}})
        product_qa({"product_id":pid,"tests":{"passed":True},"security":{"passed":True}})
        product_localize({"product_id":pid,"locales":["en"]})
        with self.assertRaises(ValueError):
            launch_candidate({"product_id":pid,"markets":[{"country":"XX","eligibility":"pending_review"}]})
        out=launch_candidate({"product_id":pid,"markets":[{"country":"US","eligibility":"allowed"}]})
        self.assertEqual(out["factory_state"],"launch_candidate")
        self.assertFalse(Product.objects.get(pk=pid).active)

    def test_worker_retry_rolls_back_factory_effect_before_replay(self):
        agent = Agent.objects.create(code="factory-retry", name="Factory retry", mission="Research", active=True)
        capability = AgentCapability.objects.create(code="product_research", name="Research", active=True)
        capability.agents.add(agent)
        task = AgentTask.objects.create(
            agent=agent, action_type="product_research", capability_code=capability.code,
            risk_snapshot="low", input_data={"title":"Retry-safe product", "sources":[
                {"url":"https://example.com/a", "finding":"demand"},
                {"url":"https://example.com/b", "finding":"competition"},
            ]},
        )

        def fail_after_effect(payload):
            product_research(payload)
            raise RuntimeError("simulated process failure after database effect")

        with self.assertRaisesRegex(RuntimeError, "simulated process failure"):
            WorkerRunner(ToolGateway([ToolSpec(code="product_research", handler=fail_after_effect)])).run(task.pk)
        task.refresh_from_db()
        self.assertEqual(task.status, "queued")
        self.assertEqual(Product.objects.filter(title="Retry-safe product").count(), 0)

        completed = WorkerRunner(ToolGateway([ToolSpec(code="product_research", handler=product_research)])).run(task.pk)
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
        brain = AutonomousBrain()

        task = brain.plan_product_factory_step({
            "title":"Farm workflow evidence digest",
            "sources":[
                {"url":"https://example.com/demand", "finding":"Small farms need a simple harvest log."},
                {"url":"https://example.com/alternatives", "finding":"Available tools are overly complex for a small operation."},
            ],
        })
        self.assertEqual(task.action_type, "product_research")
        self.assertEqual(task.status, "queued")
        self.assertTrue(AuditLog.objects.filter(action="factory_next_step_planned", target_id=str(task.pk)).exists())
        self.assertEqual(brain.plan_product_factory_step({"title":"ignored", "sources":[{}, {}]}).pk, task.pk)

        completed = WorkerRunner(build_factory_gateway()).run(task.pk)
        self.assertEqual(completed.status, "completed")
        product = Product.objects.get(pk=completed.output_data["product_id"])
        self.assertEqual(product.metadata["factory_state"], "researched")
        next_step = brain.decide_product_factory_step(product.pk)
        self.assertEqual(next_step["action"], "product_opportunity_score")
