"""Fault-correction loop for MojPlayWin manufacturing briefs, without publishing.

QA failure is a durable diagnosis and repair ticket, never product deletion.
This is the application-side state machine. VPS execution remains a separately
authorized integration, not something inferred from writing a DB row.
"""
from __future__ import annotations

from uuid import uuid4

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .mojplaywin_production_models import (
    MojPlayWinManufacturingOrder as Brief,
    MojPlayWinQADefect as Defect,
    MojPlayWinQAReview as Review,
    MojPlayWinReworkCycle as Rework,
)


class ProductionFlowError(ValueError):
    pass


def _operator(user):
    if not getattr(user, "is_authenticated", False) or not user.is_active or not user.is_staff:
        raise ProductionFlowError("Only a verified active internal operator may record production results")


def _owner(user):
    _operator(user)
    if not user.is_superuser:
        raise ProductionFlowError("Only an authorized main-site owner may initiate manufacturing requests")


def create_non_site_brief(*, origin, reference, description, product_title, file_format, deliverable, owner):
    """Register one customer, market or factory invention brief (not a sale)."""
    _owner(owner)
    if origin not in ("customer", "market", "invention"):
        raise ProductionFlowError("Use the site-card intake for site-origin proposals")
    fields = (reference, description, product_title, file_format, deliverable)
    if any(not isinstance(x, str) or not x.strip() for x in fields):
        raise ProductionFlowError("An actual source reference and a defined deliverable are required")
    with transaction.atomic():
        existing = Brief.objects.select_for_update().filter(origin_reference=reference.strip()).first()
        if existing:
            if existing.origin_type != origin:
                raise ProductionFlowError("Reference collision between different origin types")
            return existing, False
        brief = Brief(
            proposal_id="MPW-MAN-" + uuid4().hex[:20].upper(),
            origin_type=origin,
            origin_reference=reference.strip(),
            origin_description=description.strip(),
            product_title=product_title.strip(),
            file_format=file_format.strip(),
            deliverable=deliverable.strip(),
            proposed_owner=owner,
            status="proposed_for_review",
            production_stage="not_started",
        )
        brief.full_clean()
        brief.save()
        return brief, True


@transaction.atomic
def record_artifact_for_qa(*, brief_id, operator, artifact_reference, production_evidence):
    """Record an *operator-attested* delivery into QA, not proof of VPS activity."""
    _operator(operator)
    if not artifact_reference.strip() or not production_evidence.strip():
        raise ProductionFlowError("Artifact reference and traceable production evidence are required")
    brief = Brief.objects.select_for_update().get(pk=brief_id)
    if brief.status != "scoped" or not brief.proposed_owner_id:
        raise ProductionFlowError("Only reviewed, owned and scoped briefs may proceed")
    if brief.production_stage not in ("not_started", "manufacturing"):
        raise ProductionFlowError("A failed product must complete its rework ticket first")
    brief.production_stage = "qa_review"
    brief.save(update_fields=["production_stage", "updated_at"])
    return brief


def _validate_defects(items):
    if not isinstance(items, (list, tuple)) or not items:
        raise ProductionFlowError("A QA failure needs one or more actionable defect reports")
    if len(items) > 100:
        raise ProductionFlowError("Too many defect reports in one inspection")
    seen = set()
    for defect in items:
        if not isinstance(defect, dict):
            raise ProductionFlowError("Defect details must be structured")
        for key in ("defect_code", "severity", "cause", "expected", "actual", "correction_plan"):
            if not isinstance(defect.get(key), str) or not defect[key].strip():
                raise ProductionFlowError("Missing real defect cause or correction instructions: " + key)
        if defect["severity"] not in ("critical", "major", "minor"):
            raise ProductionFlowError("Invalid defect severity")
        if len(defect["defect_code"]) > 70 or defect["defect_code"] in seen:
            raise ProductionFlowError("Duplicate/invalid defect code")
        seen.add(defect["defect_code"])


@transaction.atomic
def record_quality_review(
    *, brief_id, inspector, review_key, artifact_reference,
    summary, verdict, defects=(),
):
    """Record independent QA; failed artifacts enter rework, NEVER deletion."""
    _operator(inspector)
    if verdict not in ("pass", "fail"):
        raise ProductionFlowError("Unknown QA verdict")
    if not all(isinstance(x, str) and x.strip() for x in (review_key, artifact_reference, summary)):
        raise ProductionFlowError("Review ID, artifact and actual inspection notes are required")
    brief = Brief.objects.select_for_update().get(pk=brief_id)
    existing = Review.objects.filter(review_key=review_key).first()
    if existing:
        if existing.brief_id != brief.pk or existing.verdict != verdict or existing.artifact_reference != artifact_reference:
            raise ProductionFlowError("Conflicting quality-review idempotency key")
        return existing
    if brief.production_stage != "qa_review":
        raise ProductionFlowError("QA may assess only a product awaiting inspection")
    if verdict == "fail":
        _validate_defects(defects)
    elif defects:
        raise ProductionFlowError("A pass cannot include unresolved new defects")

    older_unresolved = Defect.objects.filter(
        review__brief=brief, resolved_at__isnull=True
    ).exists()
    if older_unresolved:
        raise ProductionFlowError("All earlier QA defects need documented correction before retest")
    review = Review.objects.create(
        brief=brief,
        review_key=review_key,
        round_number=brief.quality_round + 1,
        verdict=verdict,
        artifact_reference=artifact_reference,
        summary=summary.strip(),
        reviewed_by=inspector,
    )
    brief.quality_round += 1
    if verdict == "fail":
        for spec in defects:
            Defect.objects.create(
                review=review,
                defect_code=spec["defect_code"].strip(),
                severity=spec["severity"],
                cause=spec["cause"].strip(),
                expected=spec["expected"].strip(),
                actual=spec["actual"].strip(),
                correction_plan=spec["correction_plan"].strip(),
            )
        attention = brief.quality_round >= 3
        Rework.objects.create(
            failed_review=review,
            brief=brief,
            attempt_number=brief.quality_round,
            state="needs_expert" if attention else "queued",
            instructions="\n".join(
                spec["defect_code"] + ": " + spec["correction_plan"].strip()
                for spec in defects
            ),
        )
        brief.production_stage = "attention_required" if attention else "rework_required"
    else:
        if not brief.proposed_owner_id:
            raise ProductionFlowError("Verified product ownership is required before QA acceptance")
        brief.production_stage = "qa_passed"
    brief.save(update_fields=["quality_round", "production_stage", "updated_at"])
    return review


@transaction.atomic
def start_rework(*, cycle_id, operator):
    _operator(operator)
    cycle = Rework.objects.select_for_update().select_related("brief").get(pk=cycle_id)
    brief = Brief.objects.select_for_update().get(pk=cycle.brief_id)
    if cycle.state not in ("queued", "needs_expert"):
        raise ProductionFlowError("This rework is not queued")
    if cycle.state == "needs_expert" and not operator.is_superuser:
        raise ProductionFlowError("After repeated failures, expert owner escalation is required")
    if brief.production_stage not in ("rework_required", "attention_required"):
        raise ProductionFlowError("Production stage does not require correction")
    cycle.state = "in_progress"
    cycle.save(update_fields=["state"])
    brief.production_stage = "rework_in_progress"
    brief.save(update_fields=["production_stage", "updated_at"])
    return cycle


@transaction.atomic
def document_defect_fix(*, defect_id, operator, correction_evidence):
    _operator(operator)
    if not isinstance(correction_evidence, str) or len(correction_evidence.strip()) < 15:
        raise ProductionFlowError("Explain actual correction evidence, not just a yes/no checkbox")
    defect = Defect.objects.select_for_update().select_related("review").get(pk=defect_id)
    cycle = Rework.objects.select_for_update().get(failed_review=defect.review)
    if cycle.state != "in_progress":
        raise ProductionFlowError("Defect may be closed only during active rework")
    if defect.resolved_at is not None:
        if defect.resolution_evidence != correction_evidence.strip():
            raise ProductionFlowError("Immutable defect-resolution evidence already recorded")
        return defect
    defect.resolution_evidence = correction_evidence.strip()
    defect.resolved_at = timezone.now()
    defect.resolved_by = operator
    defect.save(update_fields=["resolution_evidence", "resolved_at", "resolved_by"])
    return defect


@transaction.atomic
def submit_rework_for_retest(
    *, cycle_id, operator, updated_artifact_reference, repair_summary,
):
    _operator(operator)
    if not all(isinstance(v, str) and v.strip() for v in (updated_artifact_reference, repair_summary)):
        raise ProductionFlowError("Repaired artifact ID and a nonempty repair summary are required")
    cycle = Rework.objects.select_for_update().select_related("failed_review").get(pk=cycle_id)
    brief = Brief.objects.select_for_update().get(pk=cycle.brief_id)
    if cycle.state != "in_progress" or brief.production_stage != "rework_in_progress":
        raise ProductionFlowError("Correction is not in progress")
    if cycle.failed_review.artifact_reference == updated_artifact_reference.strip():
        raise ProductionFlowError("An updated artifact version is required for independent retest")
    if cycle.failed_review.defects.filter(resolved_at__isnull=True).exists():
        raise ProductionFlowError("Every recorded defect requires correction evidence")
    cycle.state = "ready_for_retest"
    cycle.replacement_artifact_reference = updated_artifact_reference.strip()
    cycle.fix_summary = repair_summary.strip()
    cycle.returned_at = timezone.now()
    cycle.save(update_fields=["state", "replacement_artifact_reference", "fix_summary", "returned_at"])
    brief.production_stage = "qa_review"
    brief.save(update_fields=["production_stage", "updated_at"])
    return cycle
