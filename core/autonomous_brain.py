"""Autonomous observe/decide/replan brain for the single master agent."""
from dataclasses import dataclass
from django.db import DatabaseError
from core.models import AgentTask, Product, Order, LedgerEntry, CommerceFunnelEvent

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
        # Counting our own products is a valid inventory measurement, not
        # independent evidence that buyers want an offer.  The existing
        # income_market_research tool records `database_measurement` only.
        # Keep that useful inventory step, but do not promote it to proof of
        # external demand or allow it to unlock speculative offer creation.
        latest_inventory = prerequisite_tasks.filter(
            capability_code="income_market_research",
            output_data__evidence__kind="database_measurement",
        ).order_by("-created_at", "-pk").first()
        latest_research = prerequisite_tasks.filter(
            capability_code="income_market_research",
            output_data__market_validation__status="independently_verified",
            output_data__market_validation__source_type="external_customer_demand",
            output_data__market_validation__validated_by="independent_market_evidence_adapter",
            output_data__market_validation__source_id__isnull=False,
        ).order_by("-created_at", "-pk").first()
        market_research_complete = latest_research is not None
        opportunity_scored = bool(
            latest_research
            and prerequisite_tasks.filter(
                capability_code="income_opportunity_score",
                created_at__gt=latest_research.created_at,
            ).exists()
        )
        self_improvement_complete = economic_tasks.filter(
            capability_code="master_self_improvement", status="completed",
            output_data__verified_effect=True,
        ).exists()
        self_improvement_failed = economic_tasks.filter(
            capability_code="master_self_improvement", status="failed",
        ).exists()
        self_improvement_unverified = economic_tasks.filter(
            capability_code="master_self_improvement", status="completed",
        ).exclude(output_data__verified_effect=True).exists()
        last_revenue_review = economic_tasks.filter(
            capability_code="income_revenue_verify", status="completed"
        ).order_by("-updated_at", "-pk").first()
        latest_paid_order_at = Order.objects.filter(
            status__in=("paid", "completed")
        ).order_by("-updated_at").values_list("updated_at", flat=True).first()
        latest_payment_entry_at = LedgerEntry.objects.filter(
            entry_type__in=("payment", "settlement")
        ).order_by("-created_at").values_list("created_at", flat=True).first()
        last_review_at = last_revenue_review.updated_at if last_revenue_review else None
        financial_event_needs_reconcile = any(
            seen_at is not None and (last_review_at is None or seen_at > last_review_at)
            for seen_at in (latest_paid_order_at, latest_payment_entry_at)
        )
        latest_funnel_review = economic_tasks.filter(
            capability_code="income_funnel_audit", status="completed",
        ).order_by("-updated_at", "-pk").first()
        try:
            latest_funnel_event_at = CommerceFunnelEvent.objects.order_by(
                "-created_at",
            ).values_list("created_at", flat=True).first()
        except DatabaseError:
            # A missing/unapplied commerce migration cannot crash the master.
            # This is not proof that customer activity is absent.
            latest_funnel_event_at = None
        funnel_event_needs_review = bool(
            latest_funnel_event_at is not None
            and (latest_funnel_review is None
                 or latest_funnel_event_at > latest_funnel_review.updated_at)
        )
        return {
            "unfinished_tasks": AgentTask.objects.filter(agent__code="economic-master-agent",status__in=("queued","running","blocked")).count(),
            "failed_tasks": AgentTask.objects.filter(agent__code="economic-master-agent",status="failed").count(),
            "market_research_complete": market_research_complete,
            "market_inventory_measured": latest_inventory is not None,
            "opportunity_scored": opportunity_scored,
            "active_products": products.filter(active=True).count(),
            "offer_designed": products.filter(metadata__commercial_status="offer_designed").count(),
            "mvp_built": products.filter(metadata__commercial_status="mvp_built").count(),
            "growth_ready": products.filter(metadata__commercial_status="growth_ready").count(),
            "orders": Order.objects.count(),
            "paid_orders": Order.objects.filter(status__in=("paid","completed")).count(),
            "financial_event_needs_reconcile": financial_event_needs_reconcile,
            "funnel_event_needs_review": funnel_event_needs_review,
            "self_improvement_complete": self_improvement_complete,
            "self_improvement_failed": self_improvement_failed,
            "self_improvement_unverified": self_improvement_unverified,
        }

    def candidates(self, s):
        c=[]
        if s["unfinished_tasks"]:
            return [Candidate("continue_existing_work","An unfinished task must be resolved first.",10,10,10,1)]
        # A newly recorded payment is more urgent than any internal planning
        # prerequisite. Check evidence first; never infer settled revenue.
        if s.get("financial_event_needs_reconcile", False):
            return [Candidate("income_revenue_verify", "New financial evidence needs independent reconciliation.", 10, 10, 9, 1)]
        if s.get("funnel_event_needs_review", False):
            return [Candidate(
                "income_funnel_audit",
                "New local commerce events require a read-only funnel diagnostic; telemetry is not settled cash.",
                10, 10, 9, 1,
            )]
        if s.get("self_improvement_unverified", False) and not s.get("self_improvement_complete", False):
            return [Candidate(
                "await_external_self_improvement_review",
                "The private repair engine completed without verified improvement; do not repeat it without new evidence.",
                10, 10, 10, 1,
            )]
        if not s.get("self_improvement_complete", False) and not s.get("self_improvement_failed", False):
            return [Candidate(
                "master_self_improvement",
                "Run the measured private self-improvement engine before starting the commercial cycle.",
                10, 10, 10, 1,
            )]
        # Do not design or promote an offer until research and scoring each
        # completed with a verified effect. This prevents speculative offer creation.
        if not s.get("market_inventory_measured", False) and not s["market_research_complete"]:
            return [Candidate(
                "income_market_research",
                "Measure internal inventory once before seeking real external demand evidence.",
                10, 10, 9, 1,
            )]
        if not s["market_research_complete"]:
            return [Candidate(
                "await_external_market_evidence",
                "Internal inventory is not evidence of buyer demand; a verified external market signal is required before a new offer.",
                10, 10, 10, 1,
            )]
        if not s["opportunity_scored"]:
            return [Candidate(
                "income_opportunity_score",
                "Market research is verified; score the opportunity before offer design.",
                10, 9, 9, 1,
            )]
        # Reconcile after a *new* order/payment event, not on every clock tick.
        # This does not claim actual settlement; the ledger tool still requires
        # independent provider evidence before reporting verified cash.
        if s["mvp_built"]:
            c.append(Candidate("income_growth_experiment","A built MVP exists; prepare/test acquisition.",10,9,9,2))
        if s["offer_designed"]:
            c.append(Candidate("income_mvp_build","A designed offer exists without a built MVP.",10,10,10,2))
        if (s["growth_ready"] or s["active_products"]) and not c:
            # No built MVP remains, and the current growth tool merely changes
            # metadata. Re-running it or 'profit optimization' would be a fake
            # business outcome and could repeat forever without any buyer.
            c.append(Candidate(
                "await_external_acquisition",
                "An existing offer needs an authorized real customer channel; internal metadata changes cannot create a buyer.",
                10, 10, 10, 1,
            ))
        if not s["offer_designed"] and not s["mvp_built"] and not s["growth_ready"]:
            if not s["active_products"]:
                c.append(Candidate("income_offer_design","No prepared offer exists; create one bounded offer.",9,9,8,2))
        if not c:
            c.append(Candidate(
                "await_external_evidence",
                "No new external outcome exists; do not manufacture repeated internal progress reports.",
                10, 10, 10, 1,
            ))
        return sorted(c,key=lambda x:x.score,reverse=True)

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
