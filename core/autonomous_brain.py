"""Autonomous decision brain for the single economic master agent.

No fixed business pipeline. Each iteration observes current state, generates
candidate actions, scores them, chooses one, and leaves execution to the
controlled worker/approval boundary.
"""
from dataclasses import dataclass
from core.models import AgentTask, Product, Order

@dataclass(frozen=True)
class Candidate:
    action: str
    reason: str
    impact: int
    urgency: int
    confidence: int
    risk: int
    payload: dict
    @property
    def score(self):
        return self.impact * 4 + self.urgency * 3 + self.confidence * 2 - self.risk * 3

class AutonomousBrain:
    def observe(self):
        return {
            "unfinished_tasks": AgentTask.objects.filter(
                agent__code="economic-master-agent",
                status__in=("queued","running","blocked"),
            ).count(),
            "completed_tasks": AgentTask.objects.filter(
                agent__code="economic-master-agent", status="completed"
            ).count(),
            "active_products": Product.objects.filter(active=True).count(),
            "orders": Order.objects.count(),
            "paid_orders": Order.objects.filter(status__in=("paid","completed")).count(),
        }

    def candidates(self, state):
        c = []
        if state["unfinished_tasks"]:
            c.append(Candidate("continue_existing_work","Finish existing work before inventing more.",10,10,10,1,{}))
        if state["active_products"] == 0:
            c += [
                Candidate("income_market_research","No active product: validate a market before building.",8,8,8,1,{}),
                Candidate("income_offer_design","No active product: turn validated capability into an offer.",9,7,6,2,{}),
            ]
        elif state["orders"] == 0:
            c.append(Candidate("income_growth_experiment","Product exists but has no orders; test acquisition.",10,9,7,2,{}))
        else:
            c.append(Candidate("income_revenue_verify","Orders exist; verify settlement before counting revenue.",10,10,9,1,{}))
        c.append(Candidate("income_profit_optimize","Measure current economics and find the highest-impact bottleneck.",6,5,8,1,{}))
        return sorted(c, key=lambda x: x.score, reverse=True)

    def decide(self):
        state = self.observe()
        ranked = self.candidates(state)
        chosen = ranked[0]
        return {
            "state": state,
            "chosen": {
                "action": chosen.action, "reason": chosen.reason, "score": chosen.score,
                "payload": chosen.payload,
            },
            "alternatives": [
                {"action": x.action, "reason": x.reason, "score": x.score}
                for x in ranked[1:4]
            ],
        }
