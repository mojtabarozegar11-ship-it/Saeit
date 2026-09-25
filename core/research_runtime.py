from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.text import slugify

from .models import ResearchProject, ResearchSource, Evidence, Finding, Report, KnowledgeArticle


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
        try:
            normalized_confidence = Decimal(str(confidence)) if confidence is not None else None
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ValidationError({"confidence": "Confidence must be numeric."}) from exc
        evidence = Evidence(
            project=project,
            source=source,
            passage=passage,
            confidence=normalized_confidence,
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
        try:
            normalized_confidence = Decimal(str(confidence)) if confidence is not None else None
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ValidationError({"confidence": "Confidence must be numeric."}) from exc
        finding = Finding(
            project=project,
            title=title,
            statement=statement,
            confidence=normalized_confidence,
            limitation=limitation,
        )
        finding.full_clean()
        finding.save()
        if evidence:
            finding.evidence.set(evidence)
        return finding

    @transaction.atomic
    def draft_knowledge_from_report(self, report, title=None):
        """Create an unpublished knowledge draft with explicit report provenance."""
        if report is None or not report.pk:
            raise ValidationError("A saved research report is required.")
        project = report.project
        base_title = (title or report.title or project.title).strip()
        if not base_title:
            raise ValidationError("Knowledge title is required.")
        slug_base = slugify(base_title) or f"research-report-{report.pk}"
        slug = slug_base
        suffix = 2
        while KnowledgeArticle.objects.filter(slug=slug).exists():
            slug = f"{slug_base}-{suffix}"
            suffix += 1
        content = report.content if isinstance(report.content, str) else str(report.content)
        return KnowledgeArticle.objects.create(
            source_report=report,
            title=base_title,
            slug=slug,
            content=content,
            version=1,
            published=False,
        )

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
