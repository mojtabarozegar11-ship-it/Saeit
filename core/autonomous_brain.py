"""Autonomous observe/decide/replan brain for the single master agent."""
from dataclasses import dataclass
from core.models import AgentTask, AuditLog, Product, Order

@dataclass(frozen=True)
class Candidate:
    action: str
    reason: str
    impact: int
    urgency: int
    confidence: int
    risk: int
    @property
    def score(self):
        return self.impact*4 + self.urgency*3 + self.confidence*2 - self.risk*3

class AutonomousBrain:
    def observe(self):
        products = Product.objects.all()
        economic_tasks = AgentTask.objects.filter(agent__code="economic-master-agent")
        latest_offer = economic_tasks.filter(
            capability_code="income_offer_design"
        ).order_by("-created_at", "-pk").first()
        prerequisite_tasks = economic_tasks.filter(
            status="completed", output_data__verified_effect=True
        )
        if latest_offer:
            prerequisite_tasks = prerequisite_tasks.filter(
                created_at__gt=latest_offer.created_at
            )
        latest_research = prerequisite_tasks.filter(
            capability_code="income_market_research"
        ).order_by("-created_at", "-pk").first()
        market_research_complete = latest_research is not None
        opportunity_scored = bool(
            latest_research
            and prerequisite_tasks.filter(
                capability_code="income_opportunity_score",
                created_at__gt=latest_research.created_at,
            ).exists()
        )
        return {
            "unfinished_tasks": AgentTask.objects.filter(agent__code="economic-master-agent",status__in=("queued","running","blocked")).count(),
            "failed_tasks": AgentTask.objects.filter(agent__code="economic-master-agent",status="failed").count(),
            "market_research_complete": market_research_complete,
            "opportunity_scored": opportunity_scored,
            "active_products": products.filter(active=True).count(),
            "offer_designed": products.filter(metadata__commercial_status="offer_designed").count(),
            "mvp_built": products.filter(metadata__commercial_status="mvp_built").count(),
            "growth_ready": products.filter(metadata__commercial_status="growth_ready").count(),
            "orders": Order.objects.count(),
            "paid_orders": Order.objects.filter(status__in=("paid","completed")).count(),
        }

    def candidates(self, s):
        c=[]
        if s["unfinished_tasks"]:
            return [Candidate("continue_existing_work","An unfinished task must be resolved first.",10,10,10,1)]
        # Do not design or promote an offer until research and scoring each
        # completed with a verified effect. This prevents speculative offer creation.
        if not s["market_research_complete"]:
            return [Candidate(
                "income_market_research",
                "No verified market-research task exists; collect decision evidence first.",
                10, 10, 9, 1,
            )]
        if not s["opportunity_scored"]:
            return [Candidate(
                "income_opportunity_score",
                "Market research is verified; score the opportunity before offer design.",
                10, 9, 9, 1,
            )]
        # Dependencies are inferred from observed state, not a fixed pipeline.
        if s["growth_ready"] and s["orders"]:
            c.append(Candidate("income_revenue_verify","Orders exist for commercialized work; reconcile evidence.",10,10,9,1))
        if s["mvp_built"]:
            c.append(Candidate("income_growth_experiment","A built MVP exists; prepare/test acquisition.",10,9,9,2))
        if s["offer_designed"]:
            c.append(Candidate("income_mvp_build","A designed offer exists without a built MVP.",10,10,10,2))
        if not s["offer_designed"] and not s["mvp_built"] and not s["growth_ready"]:
            c.append(Candidate("income_offer_design","No prepared offer exists; create the highest-value concrete offer.",9,9,8,2))
            c.append(Candidate("income_market_research","Commercial state is insufficient; gather decision evidence.",8,8,8,1))
        if s["active_products"] and not s["orders"]:
            c.append(Candidate("income_growth_experiment","Active product has no orders; acquisition is the bottleneck.",10,9,7,2))
        c.append(Candidate("income_profit_optimize","Measure economics and identify the next bottleneck.",6,5,8,1))
        return sorted(c,key=lambda x:x.score,reverse=True)

    def observe_product_factory(self, product_id=None):
        """Observe lifecycle state and runtime work before selecting a factory step."""
        products = Product.objects.all()
        if product_id is not None:
            products = products.filter(pk=product_id)
        products = list(products.order_by("-updated_at", "-pk"))
        if product_id is not None and not products:
            raise RuntimeError(f"Product {product_id} does not exist in the factory registry.")
        products = [
            item for item in products
            if isinstance(item.metadata, dict) and item.metadata.get("factory_state")
        ]
        product = next(
            (item for item in products if item.metadata.get("factory_state") != "launch_candidate"),
            products[0] if products else None,
        )
        tasks = AgentTask.objects.filter(action_type__startswith="product_")
        if product:
            tasks = tasks.filter(input_data__product_id=product.pk)
        else:
            tasks = tasks.filter(action_type="product_research")
        pending = tasks.filter(status__in=("queued", "running", "blocked")).order_by("created_at", "pk").first()
        latest_failure = tasks.filter(status="failed").order_by("-updated_at", "-pk").first()
        return {
            "product": product,
            "factory_state": product.metadata.get("factory_state") if product else "new",
            "pending_task": pending,
            "latest_failure": latest_failure,
            "candidate_count": Product.objects.filter(metadata__factory_state="launch_candidate").count(),
        }

    def decide_product_factory_step(self, product_id=None):
        """Select the first unmet lifecycle gate from persisted Product evidence."""
        state = self.observe_product_factory(product_id)
        if state["pending_task"]:
            task = state["pending_task"]
            return {"action": "continue_existing_task", "task_id": task.pk,
                    "reason": f"Task {task.pk} is {task.status} and must be resolved first."}
        if state["latest_failure"]:
            task = state["latest_failure"]
            return {"action": "blocked", "task_id": task.pk,
                    "reason": str((task.output_data or {}).get("error") or "Factory task failed; remediation is required.")}
        next_action = {
            "new": "product_research",
            "researched": "product_opportunity_score",
            "scored": "product_spec",
            "specified": "product_build_record",
            "built": "product_qa",
            "qa_passed": "product_localize",
            "localized": "product_launch_candidate",
            "launch_candidate": "owner_approval_boundary",
        }
        action = next_action.get(state["factory_state"])
        if not action:
            return {"action": "blocked", "reason": "Unknown factory state; lifecycle state requires review."}
        if action == "owner_approval_boundary":
            return {"action": action, "product_id": state["product"].pk,
                    "reason": "All internal gates passed. Publication remains owner-gated."}
        return {"action": action,
                "product_id": state["product"].pk if state["product"] else None,
                "reason": f"Persisted lifecycle state is {state['factory_state']}; this is the next unmet gate."}

    def plan_product_factory_step(self, payload=None, product_id=None):
        """Queue one capability-authorized step through the existing MasterAgent planner."""
        from core.orchestrator import MasterAgent

        decision = self.decide_product_factory_step(product_id)
        if decision["action"] == "continue_existing_task":
            return AgentTask.objects.get(pk=decision["task_id"])
        if decision["action"] in {"blocked", "owner_approval_boundary"}:
            raise RuntimeError(decision["reason"])
        task_payload = dict(payload or {})
        if decision["product_id"] is not None:
            task_payload["product_id"] = decision["product_id"]
        required_input = {
            "product_research": ("title", "sources"),
            "product_opportunity_score": ("score",),
            "product_spec": ("spec",),
            "product_build_record": ("artifact",),
            "product_qa": ("tests", "security"),
            "product_localize": ("locales",),
            "product_launch_candidate": ("markets",),
        }[decision["action"]]
        if any(task_payload.get(key) in (None, "", [], {}) for key in required_input):
            raise RuntimeError(
                f"The {decision['action']} agent must provide verified output fields: "
                + ", ".join(required_input)
            )
        task = MasterAgent().plan(
            project=None,
            action=decision["action"],
            payload=task_payload,
            risk="low",
        )
        AuditLog.objects.create(
            actor_type="agent",
            actor_id="factory-master-agent",
            action="factory_next_step_planned",
            target_type="AgentTask",
            target_id=str(task.pk),
            after_state={**decision, "status": task.status, "agent": task.agent.code},
            trace_id=f"factory-master-task-{task.pk}",
        )
        return task

    def decide(self):
        s=self.observe(); ranked=self.candidates(s); chosen=ranked[0]
        return {"state":s,"chosen":{"action":chosen.action,"reason":chosen.reason,"score":chosen.score},
                "alternatives":[{"action":x.action,"reason":x.reason,"score":x.score} for x in ranked[1:4]]}

    @staticmethod
    def prerequisite_from_error(error):
        e=str(error or "").lower()
        if "no built mvp" in e: return "income_mvp_build"
        if "no designed offer" in e: return "income_offer_design"
        return None
