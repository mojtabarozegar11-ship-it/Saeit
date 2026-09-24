from django.db import transaction
from .models import ResearchProject, ResearchSource, Evidence, Finding, Report

class ResearchRuntime:
    """Evidence-first research pipeline. External retrieval is injected by a tool adapter."""
    @transaction.atomic
    def register_source(self, project, title, url="", publisher="", content_hash=""):
        return ResearchSource.objects.create(project=project, title=title, url=url, publisher=publisher, content_hash=content_hash)

    @transaction.atomic
    def add_evidence(self, project, source, passage, confidence=0.0):
        return Evidence.objects.create(project=project, source=source, passage=passage, confidence=confidence)

    @transaction.atomic
    def add_finding(self, project, title, statement, evidence=(), confidence=0.0, limitation=""):
        finding = Finding.objects.create(project=project, title=title, statement=statement, confidence=confidence, limitation=limitation)
        if evidence:
            finding.evidence.set(evidence)
        return finding

    @transaction.atomic
    def create_report(self, project, title, content, version=1):
        return Report.objects.create(project=project, title=title, content=content, version=version, status="draft")
