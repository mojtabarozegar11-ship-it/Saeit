"""Independent Product Factory verification, freshness, and release gates."""
import hashlib
import json
from pathlib import Path
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.contrib.auth import get_user_model
from django.conf import settings
from django.utils import timezone

from .models import (
    AgentTask, ApprovalRequest, FactoryArtifact, FactoryEvidence, FactoryReleaseGate,
    FactoryReleaseManifest, FactoryRun, FactoryMarketEligibility, Product,
    ResearchProject,
)
from .factory_contracts import REQUIRED_OUTPUT_KEYS, EXPECTED_OUTPUT_STATE, canonical_digest

PREVIOUS_STATE = {
    "product_research": None,
    "product_opportunity_score": "researched",
    "product_spec": "scored",
    "product_build_record": "specified",
    "product_qa": "built",
    "product_localize": "qa_passed",
    "product_launch_candidate": "localized",
}
FACTORY_EVIDENCE_POLICY_VERSION = "factory-evidence-v1"
EVIDENCE_TTL_DAYS = {"product_research": 30, "product_launch_candidate": 30}

STATE_BY_ACTION = {
    "product_research": "researched",
    "product_opportunity_score": "scored",
    "product_spec": "specified",
    "product_build_record": "built",
    "product_qa": "qa_passed",
    "product_localize": "localized",
    "product_launch_candidate": "launch_candidate",
}


def prerequisite_values(action, product, run):
    if action == "product_research" or product is None:
        return {
            "state": "new", "run_id": run.run_id, "run_goal": run.goal,
            "run_constraints": run.constraints,
        }
    meta = product.metadata if isinstance(product.metadata, dict) else {}
    previous = PREVIOUS_STATE.get(action)
    values = {
        "state": previous, "product_id": product.pk, "run_id": run.run_id,
        "run_goal": run.goal, "run_constraints": run.constraints,
    }
    predecessor = {
        "product_opportunity_score": "product_research",
        "product_spec": "product_opportunity_score",
        "product_build_record": "product_spec",
        "product_qa": "product_build_record",
        "product_localize": "product_qa",
        "product_launch_candidate": "product_localize",
    }.get(action)
    if predecessor:
        evidence = run.evidence.filter(evidence_type=predecessor).order_by("-created_at", "-pk").first()
        values["lineage"] = None if not evidence else {
            "id": evidence.pk, "status": evidence.status,
            "prerequisite_digest": evidence.prerequisite_digest,
            "details_digest": digest(evidence.details),
            "freshness_policy_version": evidence.freshness_policy_version,
            "valid_until": evidence.valid_until.isoformat() if evidence.valid_until else None,
        }
    if action == "product_opportunity_score":
        values["research"] = meta.get("research")
        values["research_runtime_digest"] = research_runtime_digest(meta)
    elif action == "product_spec":
        values["opportunity"] = meta.get("opportunity")
    elif action == "product_build_record":
        values["spec"] = meta.get("spec")
        values["spec_version"] = run.current_spec_version
    elif action == "product_qa":
        artifact = FactoryArtifact.objects.filter(product=product, run=run, version=run.current_artifact_version).first()
        values["artifact"] = None if not artifact else {
            "id": artifact.pk, "version": artifact.version, "digest": artifact_content_digest(artifact),
            "spec_version": artifact.spec_version,
        }
    elif action == "product_localize":
        values["qa"] = meta.get("qa")
        values["artifact_digest"] = _current_artifact_digest(product, run)
    elif action == "product_launch_candidate":
        values["localization"] = meta.get("localization")
        values["artifact_digest"] = _current_artifact_digest(product, run)
        # This prerequisite is captured before the adapter chooses its launch
        # markets. Bind the reviewed registry snapshot so eligibility changes
        # invalidate this stage without making its own output mutate the snapshot.
        codes = sorted(FactoryMarketEligibility.objects.values_list("market_code", flat=True))
        values["market_eligibility"] = market_eligibility_snapshot(codes)
    return values


def digest(values):
    encoded = json.dumps(values, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def snapshot_for(action, product, run):
    values = prerequisite_values(action, product, run)
    return {"values": values, "digest": digest(values), "spec_version": run.current_spec_version,
            "artifact_version": run.current_artifact_version}


def research_runtime_digest(meta):
    research = meta.get("research") or {}
    records = research.get("evidence") or []
    stored_digest = digest([
        {
            "evidence_id": item.get("evidence_id"), "finding_id": item.get("finding_id"),
            "snapshot_hash": item.get("snapshot_hash"), "passage": item.get("passage"),
            "source": item.get("source"), "confidence": item.get("confidence"),
            "provenance": item.get("provenance"),
        }
        for item in records if isinstance(item, dict)
    ])
    project = ResearchProject.objects.filter(pk=research.get("research_project_id")).first()
    if not project:
        return stored_digest
    persisted = {
        "evidence": list(project.evidence.select_related("source").order_by("pk").values(
            "id", "passage", "confidence", "source_id", "source__url", "source__content_hash",
            "source__snapshot_hash", "source__provenance", "source__retrieved_at",
        )),
        "findings": [
            {"id": finding.pk, "title": finding.title, "statement": finding.statement,
             "confidence": finding.confidence, "evidence_ids": sorted(finding.evidence.values_list("pk", flat=True))}
            for finding in project.findings.order_by("pk")
        ],
        "reports": list(project.reports.order_by("version", "pk").values("id", "version", "status", "content")),
    }
    return digest({"adapter_records": stored_digest, "research_runtime": persisted})


def _current_artifact_digest(product, run):
    artifact = FactoryArtifact.objects.filter(product=product, run=run, version=run.current_artifact_version).first()
    return artifact_content_digest(artifact) if artifact else ""


def artifact_content_digest(artifact):
    if not artifact:
        return ""
    try:
        actual = hashlib.sha256(Path(artifact.reference).resolve().read_bytes()).hexdigest()
    except (OSError, ValueError):
        return ""
    return actual if actual == artifact.content_digest else ""


def market_eligibility_snapshot(codes, *, for_update=False):
    now = timezone.now()
    records = FactoryMarketEligibility.objects.filter(market_code__in=codes).order_by("market_code")
    if for_update:
        records = records.select_for_update()
    return [
        {"market_code": item.market_code, "eligibility": item.eligibility,
         "reviewed_at": item.reviewed_at.isoformat(),
         "valid_until": item.valid_until.isoformat() if item.valid_until else None,
         "evidence_reference": item.evidence_reference, "review_note": item.review_note,
         "current": item.valid_until is not None and item.valid_until > now}
        for item in records
    ]


def invalidate_stale_evidence(product):
    # Iterate until downstream records observe stale predecessor evidence.
    changed = True
    while changed:
        changed = False
        for item in FactoryEvidence.objects.filter(product=product, status=FactoryEvidence.VALID).select_related("task", "run"):
            current = snapshot_for(item.task.action_type, product, item.run)
            spec_dependent = item.evidence_type in {
                "product_spec", "product_build_record", "product_qa", "product_localize", "product_launch_candidate"
            }
            artifact_dependent = item.evidence_type in {
                "product_build_record", "product_qa", "product_localize", "product_launch_candidate"
            }
            if (
                current["digest"] != item.prerequisite_digest
                or (spec_dependent and current["spec_version"] != item.spec_version)
                or (artifact_dependent and current["artifact_version"] != item.artifact_version)
                or item.freshness_policy_version != current_evidence_policy_version()
                or item.valid_until is None or item.valid_until <= timezone.now()
            ):
                item.status = FactoryEvidence.STALE
                item.save(update_fields=["status", "updated_at"])
                changed = True


def current_evidence_policy_version():
    return str(getattr(settings, "FACTORY_EVIDENCE_POLICY_VERSION", FACTORY_EVIDENCE_POLICY_VERSION))


def evidence_expiry_for(action):
    return timezone.now() + timedelta(days=EVIDENCE_TTL_DAYS.get(action, 90))


def validate_task_prerequisites(task):
    if task.action_type == "product_research":
        return True
    if not task.factory_run_id or not task.product_id or not task.prerequisite_snapshot:
        raise ValidationError("Factory task is missing a versioned prerequisite snapshot.")
    invalidate_stale_evidence(task.product)
    snapshot = snapshot_for(task.action_type, task.product, task.factory_run)
    if snapshot["digest"] != task.prerequisite_snapshot.get("digest"):
        raise ValidationError("Factory task prerequisites are stale; downstream evidence cannot be consumed.")
    lineage = snapshot["values"].get("lineage")
    if not isinstance(lineage, dict):
        raise ValidationError("Factory task is missing its required predecessor evidence.")
    predecessor = FactoryEvidence.objects.filter(pk=lineage.get("id"), product_id=task.product_id).first()
    if (
        not predecessor or predecessor.status != FactoryEvidence.VALID
        or predecessor.freshness_policy_version != current_evidence_policy_version()
        or not predecessor.valid_until or predecessor.valid_until <= timezone.now()
    ):
        raise ValidationError("Factory task prerequisite evidence is stale, invalid, or expired.")
    return True


class FactoryTaskVerifier:
    """Independent verifier: rereads persisted state and creates version-bound evidence."""
    def verify(self, task, output):
        action = task.action_type
        if action not in STATE_BY_ACTION:
            raise ValidationError("No independent Product Factory verifier is registered.")
        if not str(task.goal or "").strip():
            raise ValidationError("Factory task has no goal.")
        if output.get("verified_effect") is not True:
            raise ValidationError("Agent success claims do not satisfy independent verification.")
        contract = task.output_contract if isinstance(task.output_contract, dict) else {}
        required = contract.get("required", [])
        if (
            required != REQUIRED_OUTPUT_KEYS[action]
            or contract.get("state") != EXPECTED_OUTPUT_STATE[action]
            or any(output.get(key) in (None, "", [], {}) for key in REQUIRED_OUTPUT_KEYS[action])
        ):
            raise ValidationError("Task output does not satisfy its declared output contract.")
        if not task.factory_run_id:
            raise ValidationError("Factory task is not attached to a persistent run.")
        run = FactoryRun.objects.select_for_update().get(pk=task.factory_run_id)
        # Current prerequisites are checked by ToolGateway before adapter execution.
        # Rechecking the original snapshot here would compare it with the effect this
        # stage has just applied (for example, newly recorded market eligibility).
        product_id = output.get("product_id") or task.product_id
        if not product_id:
            raise ValidationError("Factory output must identify the persisted Product.")
        product = Product.objects.select_for_update().get(pk=product_id)
        if product.metadata.get("factory_state") != STATE_BY_ACTION[action]:
            raise ValidationError("Persisted Product state does not match the task's expected state.")
        if action != "product_research" and product.pk != task.product_id:
            raise ValidationError("Task is bound to a different Product than its output.")
        if task.prerequisite_snapshot and action != "product_research":
            expected = task.prerequisite_snapshot
            current = expected.get("values")
            actual = prerequisite_values(action, product, run)
            # The tool has advanced the state, so compare the required evidence values only.
            for key, value in (current or {}).items():
                if key in {"state", "product_id", "run_id"}:
                    continue
                if actual.get(key) != value:
                    raise ValidationError(f"Prerequisite {key} changed during task execution.")
        artifact = None
        if action == "product_build_record":
            artifact = FactoryArtifact.objects.get(created_by_task=task)
            if artifact.product_id != product.pk or artifact.run_id != run.pk:
                raise ValidationError("Build artifact is not bound to this task's Product and Run.")
            if artifact.version != run.current_artifact_version:
                raise ValidationError("Build artifact version is not the current Run version.")
        if action == "product_launch_candidate":
            if product.active or product.metadata.get("owner_publish_approval_required") is not True:
                raise ValidationError("Release must remain behind the owner approval gate.")
            artifact = FactoryArtifact.objects.filter(product=product, version=run.current_artifact_version).first()
            if not artifact:
                raise ValidationError("Release candidate has no versioned build artifact.")
            FactoryReleaseGate.objects.update_or_create(
                product=product,
                defaults={"run": run, "artifact": artifact, "manifest": None,
                          "status": "pending_owner_approval", "approval": None,
                          "approved_by": None, "approved_at": None},
            )
        current = snapshot_for(action, product, run)
        output.update({
            "run_id": run.run_id, "product_id": product.pk,
            "prerequisite_digest": (task.prerequisite_snapshot or {}).get("digest", current["digest"]),
            "spec_version": run.current_spec_version,
            "artifact_version": run.current_artifact_version,
        })
        if artifact:
            output.update({"artifact_id": artifact.pk, "artifact_ref": artifact.reference})
        evidence, _ = FactoryEvidence.objects.update_or_create(
            task=task, evidence_type=action,
            defaults={
                "run": run, "product": product,
                "prerequisite_digest": (task.prerequisite_snapshot or {}).get("digest", current["digest"]),
                "spec_version": run.current_spec_version,
                "artifact_version": run.current_artifact_version,
                "status": FactoryEvidence.VALID,
                "freshness_policy_version": current_evidence_policy_version(),
                "valid_until": evidence_expiry_for(action),
                "details": {"output": output, "verified_state": product.metadata.get("factory_state")},
            },
        )
        run.product = product
        run.save(update_fields=["product", "updated_at"])
        task.product = product
        task.save(update_fields=["product", "updated_at"])
        invalidate_stale_evidence(product)
        if action == "product_launch_candidate":
            gate = FactoryReleaseGate.objects.get(product=product)
            gate.manifest = create_release_manifest(product, run, gate.artifact)
            gate.save(update_fields=["manifest", "updated_at"])
            # An activation request opened before the final evidence existed is
            # rebound to the release snapshot before its owner can decide it.
            for request in ApprovalRequest.objects.filter(
                action_type="activate_product", target_type="Product",
                target_id=str(product.pk), status="pending",
            ):
                request.release_manifest_digest = gate.manifest.manifest_digest
                request.save(update_fields=["release_manifest_digest", "updated_at"])
        return evidence


@transaction.atomic
def approve_release(product, owner, approval_request):
    if not owner or not owner.is_superuser:
        raise ValidationError("Only the owner may approve Product activation.")
    current_approval = ApprovalRequest.objects.select_for_update().get(pk=approval_request.pk)
    gate = FactoryReleaseGate.objects.select_for_update().get(product_id=product.pk)
    run = FactoryRun.objects.select_for_update().get(pk=gate.run_id)
    artifact = FactoryArtifact.objects.select_for_update().get(pk=gate.artifact_id)
    manifest = FactoryReleaseManifest.objects.get(pk=gate.manifest_id) if gate.manifest_id else None
    current_product = Product.objects.select_for_update().get(pk=product.pk)
    invalidate_stale_evidence(current_product)
    if current_approval.status != "approved" or current_approval.revoked_at or not current_approval.expires_at or (
        current_approval.expires_at <= timezone.now()
    ):
        raise ValidationError("A current, non-revoked owner ApprovalRequest is required.")
    if gate.status != "pending_owner_approval":
        raise ValidationError("Release gate is not awaiting owner approval.")
    if artifact.version != run.current_artifact_version:
        raise ValidationError("Release artifact is stale.")
    if (
        current_approval.action_type != "activate_product"
        or current_approval.target_type != "Product"
        or current_approval.target_id != str(current_product.pk)
        or not manifest
        or current_approval.release_manifest_digest != manifest.manifest_digest
        or not release_manifest_is_current(manifest, current_product, run, artifact)
    ):
        raise ValidationError("Approval is not bound to this current release manifest, artifact, and activation action.")
    gate.status = "approved"
    gate.approval = current_approval
    gate.approved_by = owner
    gate.approved_at = timezone.now()
    gate.save(update_fields=["status", "approval", "approved_by", "approved_at", "updated_at"])
    return gate


@transaction.atomic
def assert_activation_allowed(product):
    if not product.is_factory_managed:
        return
    current_product = Product.objects.select_for_update().get(pk=product.pk)
    if not current_product.is_factory_managed:
        return
    invalidate_stale_evidence(current_product)
    gate = FactoryReleaseGate.objects.select_for_update().filter(product_id=current_product.pk).first()
    if not gate or gate.status != "approved" or not gate.approval_id or not gate.approved_by_id:
        raise ValidationError("Product Factory activation is blocked by the shared owner Release Gate.")
    approval = ApprovalRequest.objects.select_for_update().get(pk=gate.approval_id)
    run = FactoryRun.objects.select_for_update().get(pk=gate.run_id)
    artifact = FactoryArtifact.objects.select_for_update().get(pk=gate.artifact_id)
    manifest = FactoryReleaseManifest.objects.get(pk=gate.manifest_id) if gate.manifest_id else None
    owner = get_user_model().objects.select_for_update().get(pk=gate.approved_by_id)
    if (
        not owner.is_superuser or approval.status != "approved" or approval.revoked_at
        or not approval.expires_at or approval.expires_at <= timezone.now()
        or approval.action_type != "activate_product" or approval.target_type != "Product"
        or approval.target_id != str(current_product.pk) or not gate.approved_at
        or artifact.version != run.current_artifact_version or not manifest
        or approval.release_manifest_digest != manifest.manifest_digest
        or not release_manifest_is_current(manifest, current_product, run, artifact)
    ):
        raise ValidationError("Release approval is revoked, expired, unrelated, or stale.")


def _assert_release_evidence_current(run, product, artifact):
    required = {
        "product_research", "product_opportunity_score", "product_spec", "product_build_record",
        "product_qa", "product_localize", "product_launch_candidate",
    }
    items = {item.evidence_type: item for item in run.evidence.select_for_update().all()}
    if not required.issubset(items) or any(items[key].status != FactoryEvidence.VALID for key in required):
        raise ValidationError("Release requires current, valid evidence for every Factory stage.")
    for key in required:
        item = items[key]
        if (
            item.freshness_policy_version != current_evidence_policy_version()
            or not item.valid_until or item.valid_until <= timezone.now()
        ):
            raise ValidationError(f"Release evidence {key} is expired or uses an obsolete freshness policy.")
        snapshot = snapshot_for(key, product, run)
        if item.prerequisite_digest != snapshot["digest"]:
            raise ValidationError(f"Release evidence {key} has stale prerequisites.")
    qa = (product.metadata.get("qa") or {})
    if not qa.get("tests", {}).get("passed") or not qa.get("security", {}).get("passed"):
        raise ValidationError("Current QA and Security evidence must pass.")
    locales = (product.metadata.get("localization") or {}).get("launch_locales") or []
    if not locales:
        raise ValidationError("Release manifest requires current localization evidence.")
    markets = (product.metadata.get("market_eligibility") or [])
    codes = [str(item.get("market_code") or "").upper() for item in markets if isinstance(item, dict)]
    eligibility = market_eligibility_snapshot(codes, for_update=True)
    if not codes or len(eligibility) != len(set(codes)) or not any(
        item["eligibility"] == FactoryMarketEligibility.ALLOWED and item["current"] for item in eligibility
    ) or any(item["eligibility"] != FactoryMarketEligibility.ALLOWED or not item["current"] for item in eligibility):
        raise ValidationError("Market eligibility is missing, expired, or no longer allowed.")
    if not artifact_content_digest(artifact) or artifact.content_digest != (product.metadata.get("build") or {}).get("sha256"):
        raise ValidationError("Release artifact digest differs from the Product build record.")


def canonical_spec_digest(spec):
    canonical = dict(spec or {})
    canonical.pop("digest", None)
    return canonical_digest(canonical)


def _manifest_snapshot(product, run, artifact):
    _assert_release_evidence_current(run, product, artifact)
    spec = product.metadata.get("spec") or {}
    evidence = list(run.evidence.order_by("evidence_type").values(
        "evidence_type", "prerequisite_digest", "spec_version", "artifact_version", "status", "details"
    ))
    markets = product.metadata.get("market_eligibility") or []
    codes = sorted({str(item.get("market_code") or "").upper() for item in markets if isinstance(item, dict)})
    return {
        "run_id": run.run_id, "product_id": product.pk, "spec_version": run.current_spec_version,
        "spec_digest": canonical_spec_digest(spec), "artifact_id": artifact.pk,
        "artifact_digest": artifact_content_digest(artifact), "artifact_version": artifact.version,
        "locales": sorted((product.metadata.get("localization") or {}).get("launch_locales") or []),
        "markets": sorted(markets, key=lambda item: item.get("market_code", "")),
        "policy_version": str(getattr(settings, "FACTORY_POLICY_VERSION", "factory-policy-v1")),
        "evidence_policy_version": current_evidence_policy_version(),
        "evidence_digest": digest(evidence), "eligibility_digest": digest(market_eligibility_snapshot(codes)),
    }


def create_release_manifest(product, run, artifact):
    snapshot = _manifest_snapshot(product, run, artifact)
    manifest_digest = digest(snapshot)
    manifest, _ = FactoryReleaseManifest.objects.get_or_create(
        manifest_digest=manifest_digest,
        defaults={
            "run": run, "product": product, "artifact": artifact,
            "spec_version": snapshot["spec_version"], "spec_digest": snapshot["spec_digest"],
            "artifact_digest": snapshot["artifact_digest"], "locales": snapshot["locales"],
            "markets": snapshot["markets"], "policy_version": snapshot["policy_version"],
            "evidence_digest": snapshot["evidence_digest"], "eligibility_digest": snapshot["eligibility_digest"],
            "snapshot": snapshot,
        },
    )
    return manifest


def release_manifest_is_current(manifest, product, run, artifact):
    try:
        return manifest.manifest_digest == digest(_manifest_snapshot(product, run, artifact))
    except (ValidationError, TypeError, ValueError):
        return False


def bind_release_approval(approval_request):
    """Bind a pending Product activation request before it can be approved."""
    if (approval_request.action_type, approval_request.target_type) != ("activate_product", "Product"):
        return
    try:
        product = Product.objects.get(pk=approval_request.target_id)
        gate = product.factory_release_gate
    except (Product.DoesNotExist, FactoryReleaseGate.DoesNotExist):
        return
    if not product.is_factory_managed:
        return
    invalidate_stale_evidence(product)
    artifact = gate.artifact
    manifest = create_release_manifest(product, gate.run, artifact)
    gate.manifest = manifest
    gate.status = "pending_owner_approval"
    gate.save(update_fields=["manifest", "status", "updated_at"])
    approval_request.release_manifest_digest = manifest.manifest_digest
