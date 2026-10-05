from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from core.autonomous_brain import AutonomousBrain
from core.models import Agent, AgentTask


def test_market_research_and_scoring_are_verified_before_offer_design():
    brain = AutonomousBrain()
    state = {
        "unfinished_tasks": 0,
        "failed_tasks": 0,
        "market_research_complete": False,
        "opportunity_scored": False,
        "active_products": 0,
        "offer_designed": 0,
        "mvp_built": 0,
        "growth_ready": 0,
        "orders": 0,
        "paid_orders": 0,
    }

    assert brain.candidates(state)[0].action == "income_market_research"

    state["market_research_complete"] = True
    assert brain.candidates(state)[0].action == "income_opportunity_score"

    state["opportunity_scored"] = True
    assert brain.candidates(state)[0].action == "income_offer_design"



class VerifiedEconomicCycleTests(TestCase):
    def setUp(self):
        self.agent = Agent.objects.create(
            code="economic-master-agent",
            name="Economic Master Agent",
            mission="Test-only economic cycle",
            active=True,
        )

    def add_task(self, capability, created_at):
        task = AgentTask.objects.create(
            agent=self.agent,
            capability_code=capability,
            status="completed",
            output_data={"verified_effect": True},
        )
        AgentTask.objects.filter(pk=task.pk).update(created_at=created_at)
        return task

    def test_prerequisite_evidence_must_follow_latest_offer_and_be_ordered(self):
        now = timezone.now()
        self.add_task("income_market_research", now - timedelta(days=3))
        self.add_task("income_opportunity_score", now - timedelta(days=2))
        self.add_task("income_offer_design", now - timedelta(days=1))

        brain = AutonomousBrain()
        state = brain.observe()
        self.assertFalse(state["market_research_complete"])
        self.assertFalse(state["opportunity_scored"])

        self.add_task("income_opportunity_score", now - timedelta(hours=2))
        state = brain.observe()
        self.assertFalse(state["market_research_complete"])
        self.assertFalse(state["opportunity_scored"])

        self.add_task("income_market_research", now - timedelta(hours=1))
        state = brain.observe()
        self.assertTrue(state["market_research_complete"])
        self.assertFalse(state["opportunity_scored"])

        self.add_task("income_opportunity_score", now)
        state = brain.observe()
        self.assertTrue(state["market_research_complete"])
        self.assertTrue(state["opportunity_scored"])
