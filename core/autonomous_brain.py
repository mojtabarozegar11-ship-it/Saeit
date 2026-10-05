"""Autonomous observe/decide/replan brain for the single master agent."""
from dataclasses import dataclass
import uuid
from django.conf import settings
from django.utils import timezone
from core.models import AgentTask, AuditLog, FactoryMarketEligibility, FactoryRun, Product, Order
from core.factory_governance import snapshot_for
from core.factory_contracts import validate_task_intent

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

    def observe_product_factory(self, product_id=None, run_id=None):
        """Observe lifecycle state and runtime work before selecting a factory step."""
        products = Product.objects.all()
        if product_id is not None:
            products = products.filter(pk=product_id)
        products = list(products.order_by("-updated_at", "-pk"))
        if product_id is not None and not products:
            raise RuntimeError(f"Product {product_id} does not exist in the factory registry.")
        products = [item for item in products if item.is_factory_managed]
        if product_id is not None and not products:
            raise RuntimeError(f"Product {product_id} is not registered in the Product Factory lifecycle.")
        product = next(
            (item for item in products if (item.metadata or {}).get("factory_state") != "launch_candidate"),
            products[0] if products else None,
        )
        tasks = AgentTask.objects.filter(action_type__startswith="product_")
        if run_id:
            tasks = tasks.filter(factory_run__run_id=run_id)
        if product:
            tasks = tasks.filter(product_id=product.pk)
        else:
            tasks = tasks.filter(action_type="product_research")
        pending = tasks.filter(status__in=("queued", "running", "blocked")).order_by("created_at", "pk").first()
        latest_failure = tasks.filter(status="failed").order_by("-updated_at", "-pk").first()
        evidence_valid = product is None
        if product:
            history = product.metadata.get("factory_history") or []
            if history and isinstance(history[-1], dict):
                latest_effect = history[-1]
                verified_task = AgentTask.objects.filter(
                    pk=latest_effect.get("task_id"),
                    status="completed",
                    action_type=latest_effect.get("action"),
                    execution_id=latest_effect.get("execution_id"),
                    output_data__product_id=product.pk,
                    output_data__verified_effect=True,
                ).exists()
                evidence_valid = (
                    verified_task
                    and latest_effect.get("state") == product.metadata.get("factory_state")
                )
                if evidence_valid and product.metadata.get("factory_state") == "launch_candidate":
                    markets = product.metadata.get("market_eligibility") or []
                    reviewed = {
                        item.market_code: item
                        for item in FactoryMarketEligibility.objects.filter(
                            market_code__in=[
                                item.get("market_code") for item in markets if isinstance(item, dict)
                            ], reviewed_by__is_superuser=True
                        ).select_related("reviewed_by")
                    }
                    now = timezone.now()
                    evidence_valid = any(
                        isinstance(item, dict)
                        and (record := reviewed.get(item.get("market_code"))) is not None
                        and record.eligibility == FactoryMarketEligibility.ALLOWED
                        and record.eligibility == item.get("eligibility")
                        and (record.valid_until is None or record.valid_until > now)
                        and bool(record.evidence_reference and record.review_note.strip() and record.valid_until)
                        for item in markets
                    )
        return {
            "product": product,
            "factory_state": (product.metadata or {}).get("factory_state") if product else "new",
            "pending_task": pending,
            "latest_failure": latest_failure,
            "evidence_valid": evidence_valid,
            "candidate_count": Product.objects.filter(metadata__factory_state="launch_candidate").count(),
        }

    def decide_product_factory_step(self, product_id=None, run_id=None):
        """Select the first unmet lifecycle gate from persisted Product evidence."""
        state = self.observe_product_factory(product_id, run_id=run_id)
        run = FactoryRun.objects.filter(run_id=run_id).first() if run_id else (
            FactoryRun.objects.filter(product_id=product_id).order_by("-created_at", "-pk").first() if product_id else None
        )
        if run and run.status == "rejected":
            return {"action": "stopped", "reason": "Evidence-backed Validation rejected this opportunity; no build work will be scheduled."}
        if run and run.status == "blocked":
            return {"action": "blocked", "reason": "Factory Run is durably blocked and requires the stated remediation."}
        if state["pending_task"]:
            task = state["pending_task"]
            if task.status == "blocked":
                return {"action": "blocked", "task_id": task.pk,
                        "reason": str((task.output_data or {}).get("error") or "Factory task is durably blocked.")}
            return {"action": "continue_existing_task", "task_id": task.pk,
                    "reason": f"Task {task.pk} is {task.status} and must be resolved first."}
        if not state["evidence_valid"]:
            return {"action": "blocked", "reason": "Current Product state has no matching completed, verified AgentTask evidence."}
        if state["latest_failure"]:
            task = state["latest_failure"]
            return {"action": "blocked", "task_id": task.pk,
                    "reason": str((task.output_data or {}).get("error") or "Factory task failed; remediation is required.")}
        next_action = {
            "new": "product_research",
            "researched": "product_opportunity_score",
            "scored": "product_validation",
            "validated": "product_spec",
            "needs_research": "product_research",
            "specified": "product_build_record",
            "built": "product_test",
            "tested": "product_security",
            "security_verified": "product_localize",
            "localized": "product_market_eligibility",
            "eligible": "product_qa",
            "qa_passed": "product_launch_candidate",
            "launch_candidate": "owner_approval_boundary",
        }
        action = next_action.get(state["factory_state"])
        if state["factory_state"] == "rejected":
            return {"action": "stopped", "reason": "The Product opportunity was rejected by Validation."}
        if not action:
            return {"action": "blocked", "reason": "Unknown factory state; lifecycle state requires review."}
        if action == "owner_approval_boundary":
            return {"action": action, "product_id": state["product"].pk,
                    "reason": "All internal gates passed. Publication remains owner-gated."}
        if action == "product_research" and state["factory_state"] == "needs_research":
            run = FactoryRun.objects.filter(run_id=run_id).first() if run_id else (
                FactoryRun.objects.filter(product_id=state["product"].pk).order_by("-created_at", "-pk").first()
            )
            attempts = run.tasks.filter(action_type="product_research").count() if run else 0
            if attempts >= 2:
                return {"action": "blocked", "reason": "Bounded re-research limit was reached; owner review is required."}
        return {"action": action,
                "product_id": state["product"].pk if state["product"] else None,
                "reason": f"Persisted lifecycle state is {state['factory_state']}; this is the next unmet gate."}

    def plan_product_factory_step(self, payload=None, product_id=None, run_id=None):
        """Queue one capability-authorized step through the existing MasterAgent planner."""
        from core.orchestrator import MasterAgent

        existing_run = FactoryRun.objects.filter(run_id=run_id).first() if run_id else None
        if existing_run and not product_id:
            product_id = existing_run.product_id
        decision = self.decide_product_factory_step(product_id, run_id=run_id)
        if decision["action"] == "continue_existing_task":
            return AgentTask.objects.get(pk=decision["task_id"])
        if decision["action"] in {"blocked", "stopped", "owner_approval_boundary"}:
            raise RuntimeError(decision["reason"])
        request = dict(payload or {})
        goal = str(request.get("goal") or decision["reason"]).strip()
        if not goal:
            raise RuntimeError("A goal is required to plan Factory work.")
        intent = dict(request)
        intent["goal"] = goal
        try:
            validate_task_intent(intent)
        except ValueError as exc:
            raise RuntimeError(str(exc)) from exc
        action = decision["action"]
        contracts = {
            "product_research": ["title", "sources"],
            "product_opportunity_score": ["score", "rationale", "rubric"],
            "product_validation": ["validation"],
            "product_spec": ["spec"],
            "product_build_record": ["artifact"],
            "product_test": ["tests"],
            "product_security": ["security"],
            "product_localize": ["localization"],
            "product_market_eligibility": ["markets"],
            "product_qa": ["qa"],
            "product_launch_candidate": ["launch_candidate"],
        }
        product = Product.objects.filter(pk=decision["product_id"]).first() if decision["product_id"] else None
        if product:
            runs = FactoryRun.objects.filter(product=product, status="active")
            if run_id:
                runs = runs.filter(run_id=run_id)
            run = runs.order_by("-created_at", "-pk").first()
            if not run:
                raise RuntimeError("Product has no active Factory Run.")
        else:
            run = existing_run
            if run and run.goal != goal:
                raise RuntimeError("A resumed Factory Run must keep its original goal.")
            if not run:
                run = FactoryRun.objects.create(
                    run_id=run_id or uuid.uuid4().hex, goal=goal,
                    constraints=request.get("constraints", []),
                    environment=str(getattr(settings, "FACTORY_ENVIRONMENT", "development")),
                )
        constraints = request.get("constraints", run.constraints)
        if not isinstance(constraints, (list, dict)):
            raise RuntimeError("Factory constraints must be a JSON object or list.")
        if run.tasks.exists() and constraints != run.constraints:
            raise RuntimeError("Constraints are immutable after a Factory Run has tasks.")
        if constraints != run.constraints:
            run.constraints = constraints
            run.save(update_fields=["constraints", "updated_at"])
        if run.status != "active":
            raise RuntimeError(f"Factory Run cannot continue from status {run.status}.")
        existing_task = run.tasks.filter(status__in=("queued", "running", "blocked")).order_by("created_at", "pk").first()
        if existing_task:
            return existing_task
        task_payload = {"goal": goal, "run_id": run.run_id}
        if constraints:
            task_payload["constraints"] = constraints
        if product:
            task_payload["product_id"] = product.pk
        task = MasterAgent().plan(
            project=None,
            action=decision["action"],
            payload=task_payload,
            risk="low",
        )
        task.goal = goal
        task.factory_run = run
        task.product = product
        task.output_contract = {"required": contracts[action], "state": {
            "product_research": "researched", "product_opportunity_score": "scored",
            "product_validation": "validated", "product_spec": "specified", "product_build_record": "built",
            "product_test": "tested", "product_security": "security_verified", "product_localize": "localized",
            "product_market_eligibility": "eligible", "product_qa": "qa_passed", "product_launch_candidate": "launch_candidate",
        }[action]}
        task.environment = run.environment
        task.input_data = task_payload
        task.prerequisite_snapshot = snapshot_for(action, product, run)
        task.save(update_fields=["goal", "factory_run", "product", "output_contract", "environment",
                                 "input_data", "prerequisite_snapshot", "updated_at"])
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
