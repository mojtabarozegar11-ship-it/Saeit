from django.core.management.base import BaseCommand
from django.db import transaction
from core.models import Agent, AgentCapability

CAPABILITIES=[
("product_research","Market Research","Collect source-backed demand and competitor evidence.","low"),
("product_opportunity_score","Opportunity Score","Score evidence-backed opportunities.","low"),
("product_spec","Product Spec","Create measurable product specifications.","medium"),
("product_build_record","Build Record","Register versioned build artifacts.","medium"),
("product_qa","QA and Security","Require passing test and security evidence.","medium"),
("product_localize","Localization","Prepare validated launch locales.","medium"),
("product_launch_candidate","Launch Candidate","Prepare eligible markets for owner-gated publication.","medium"),
]

class Command(BaseCommand):
    help="Seed the autonomous Product Factory Master Agent idempotently."
    @transaction.atomic
    def handle(self,*args,**kwargs):
        caps=[]
        for code,name,description,risk in CAPABILITIES:
            cap,_=AgentCapability.objects.update_or_create(code=code,defaults={"name":name,"description":description,"risk_level":risk,"active":True})
            caps.append(cap)
        agent,_=Agent.objects.update_or_create(code="factory-master-agent",defaults={
            "name":"Zomorod Factory Master Agent",
            "mission":"Research, score, specify, build, test, localize and prepare lawful digital products for launch candidate status.",
            "risk_level":"medium","active":True})
        agent.capabilities.set(caps)
        self.stdout.write(self.style.SUCCESS("Factory Master Agent seeded."))
