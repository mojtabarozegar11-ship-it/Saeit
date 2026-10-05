from django.core.management.base import BaseCommand
from django.db import transaction
from datetime import timedelta
from django.utils import timezone
from core.models import Agent, AgentCapability, AgentToolGrant

CAPABILITIES=[
("product_research","Market Research","Collect source-backed demand and competitor evidence.","low"),
("product_opportunity_score","Opportunity Score","Score evidence-backed opportunities.","low"),
("product_validation","Opportunity Validation","Independently validate commercial and technical assumptions before specification.","low"),
("product_spec","Product Spec","Create measurable product specifications.","medium"),
("product_build_record","Build Record","Register versioned build artifacts.","medium"),
("product_test","Independent Test","Independently test the exact immutable build artifact.","medium"),
("product_security","Independent Security","Independently verify security of the exact build artifact.","medium"),
("product_localize","Localization","Prepare release-bound locale attestations.","medium"),
("product_market_eligibility","Market Eligibility","Read and bind owner-reviewed market eligibility.","medium"),
("product_qa","Independent QA","Attest complete release lineage before launch candidacy.","medium"),
("product_launch_candidate","Launch Candidate","Record a verified inactive launch candidate.","medium"),
]

SPECIALISTS = {
    "product_research": ("factory-market-research-agent", "Market Research Agent", "Collect and qualify source-backed market evidence."),
    "product_opportunity_score": ("factory-opportunity-scoring-agent", "Opportunity Scoring Agent", "Score opportunities from persisted research evidence."),
    "product_validation": ("factory-opportunity-validation-agent", "Opportunity Validation Agent", "Validate commercial assumptions cheaply before building."),
    "product_spec": ("factory-product-strategist-agent", "Product Strategist", "Turn validated opportunities into measurable product specifications."),
    "product_build_record": ("factory-product-builder-agent", "Product Builder Agent", "Produce and register versioned product build artifacts."),
    "product_test": ("factory-independent-test-agent", "Independent Test Agent", "Test immutable build artifacts independently from Builder."),
    "product_security": ("factory-independent-security-agent", "Independent Security Agent", "Security-verify immutable build artifacts independently from Builder."),
    "product_localize": ("factory-localization-agent", "Localization Agent", "Produce release-bound locale attestations with English fallback and RTL metadata."),
    "product_market_eligibility": ("factory-market-eligibility-agent", "Market Eligibility Agent", "Bind owner-reviewed market decisions without self-approval."),
    "product_qa": ("factory-independent-qa-agent", "Independent QA Agent", "Verify exact release lineage across build, test, security, localization and eligibility."),
    "product_launch_candidate": ("factory-launch-candidate-agent", "Launch Candidate Agent", "Record an inactive verified candidate for the owner-gated publication boundary."),
}

class Command(BaseCommand):
    help="Seed the autonomous Product Factory Master Agent idempotently."
    @transaction.atomic
    def handle(self,*args,**kwargs):
        specialists=[]
        for code,name,description,risk in CAPABILITIES:
            cap,_=AgentCapability.objects.update_or_create(code=code,defaults={"name":name,"description":description,"risk_level":risk,"active":True})
            agent_code,agent_name,mission=SPECIALISTS[code]
            agent,_=Agent.objects.update_or_create(code=agent_code,defaults={
                "name":agent_name,"mission":mission,"risk_level":risk,"active":True})
            agent.capabilities.set([cap])
            AgentToolGrant.objects.update_or_create(
                agent=agent, capability_code=code, tool_code=code,
                resource_scope="product:*", environment="development",
                defaults={"active": True, "revoked_at": None,
                          "valid_until": timezone.now() + timedelta(days=1)},
            )
            specialists.append(agent)
        agent,_=Agent.objects.update_or_create(code="factory-master-agent",defaults={
            "name":"Zomorod Factory Master Agent",
            "mission":"Observe Product Factory state, select qualified specialist agents, enforce lifecycle gates and replan blocked work.",
            "risk_level":"medium","active":True})
        agent.capabilities.clear()
        self.stdout.write(self.style.SUCCESS(
            f"Factory Master Agent and {len(specialists)} specialist agents seeded."
        ))
