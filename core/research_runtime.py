from django.core.exceptions import ValidationError
from django.db import transaction

from .models import ResearchProject, ResearchSource, Evidence, Finding, Report


class ResearchRuntime:
    """Evidence-first research pipeline with project-boundary validation."""

    @transaction.atomic
    def register_source(self, project, title, url="", publisher="", content_hash=""):
        source = ResearchSource(
            project=project,
            title=title,
            url=url,
            publisher=publisher,
            content_hash=content_hash,
        )
        source.full_clean()
        source.save()
        return source

    @transaction.atomic
    def add_evidence(self, project, source, passage, confidence=0.0):
        if source.project_id != project.id:
            raise ValidationError("Evidence source must belong to the same research project.")
        evidence = Evidence(
            project=project,
            source=source,
            passage=passage,
            confidence=confidence,
        )
        evidence.full_clean()
        evidence.save()
        return evidence

    @transaction.atomic
    def add_finding(self, project, title, statement, evidence=(), confidence=0.0, limitation=""):
        evidence = tuple(evidence or ())
        invalid = [item.pk for item in evidence if item.project_id != project.id]
        if invalid:
            raise ValidationError(
                f"Finding evidence must belong to the same research project: {invalid}"
            )
        finding = Finding(
            project=project,
            title=title,
            statement=statement,
            confidence=confidence,
            limitation=limitation,
        )
        finding.full_clean()
        finding.save()
        if evidence:
            finding.evidence.set(evidence)
        return finding

    @transaction.atomic
    def create_report(self, project, title, content, version=1):
        report = Report(
            project=project,
            title=title,
            content=content,
            version=version,
            status="draft",
        )
        report.full_clean()
        report.save()
        return report
