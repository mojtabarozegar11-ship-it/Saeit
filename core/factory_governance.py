"""Independent Product Factory verification, freshness, and release gates."""
import hashlib
import json

from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import (
    AgentTask, FactoryArtifact, FactoryEvidence, FactoryReleaseGate,
    FactoryRun, Product,
)

PREVIOUS_STATE = {
    "product_research": None,
    "product_opportunity_score": "researched",
    "product_spec": "scored",
    "product_build_record": "specified",
    "product_qa": "built",
    "product_localize": "qa_passed",
    "product_launch_candidate": "localized",
}
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
    if action == "product_opportunity_score":
        values["research"] = meta.get("research")
    elif action == "product_spec":
        values["opportunity"] = meta.get("opportunity")
    elif action == "product_build_record":
        values["spec"] = meta.get("spec")
        values["spec_version"] = run.current_spec_version
    elif action == "product_qa":
        values["artifact_version"] = run.current_artifact_version
    elif action == "product_localize":
        values["qa"] = meta.get("qa")
        values["artifact_version"] = run.current_artifact_version
    elif action == "product_launch_candidate":
        values["localization"] = meta.get("localization")
        values["artifact_version"] = run.current_artifact_version
    return values


def digest(values):
    encoded = json.dumps(values, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def snapshot_for(action, product, run):
    values = prerequisite_values(action, product, run)
    return {"values": values, "digest": digest(values), "spec_version": run.current_spec_version,
            "artifact_version": run.current_artifact_version}


def invalidate_stale_evidence(product):
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
        ):
            item.status = FactoryEvidence.STALE
            item.save(update_fields=["status", "updated_at"])


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
        if not isinstance(required, list) or any(output.get(key) in (None, "", [], {}) for key in required):
            raise ValidationError("Task output does not satisfy its declared output contract.")
        if not task.factory_run_id:
            raise ValidationError("Factory task is not attached to a persistent run.")
        run = FactoryRun.objects.select_for_update().get(pk=task.factory_run_id)
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
                defaults={"run": run, "artifact": artifact, "status": "pending_owner_approval"},
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
                "details": {"output": output, "verified_state": product.metadata.get("factory_state")},
            },
        )
        run.product = product
        run.save(update_fields=["product", "updated_at"])
        task.product = product
        task.save(update_fields=["product", "updated_at"])
        invalidate_stale_evidence(product)
        return evidence


def approve_release(product, owner, approval_request):
    if not owner or not owner.is_superuser:
        raise ValidationError("Only the owner may approve Product activation.")
    gate = FactoryReleaseGate.objects.select_for_update().select_related("run", "artifact").get(product=product)
    invalidate_stale_evidence(product)
    if approval_request.status != "approved":
        raise ValidationError("A completed owner ApprovalRequest is required.")
    required_evidence = {
        "product_research", "product_opportunity_score", "product_spec",
        "product_build_record", "product_qa", "product_localize", "product_launch_candidate",
    }
    evidence_by_type = {
        item.evidence_type: item
        for item in gate.run.evidence.filter(status=FactoryEvidence.VALID)
    }
    valid = required_evidence.issubset(evidence_by_type)
    if valid:
        for evidence_type in required_evidence:
            item = evidence_by_type[evidence_type]
            if evidence_type in {"product_spec", "product_build_record", "product_qa", "product_localize", "product_launch_candidate"}:
                valid = valid and item.spec_version == gate.run.current_spec_version
            if evidence_type in {"product_build_record", "product_qa", "product_localize", "product_launch_candidate"}:
                valid = valid and item.artifact_version == gate.run.current_artifact_version
    if not valid:
        raise ValidationError("All current Run evidence must pass verification before owner approval.")
    if gate.status != "pending_owner_approval":
        raise ValidationError("Release gate is not awaiting owner approval.")
    if gate.artifact.version != gate.run.current_artifact_version:
        raise ValidationError("Release artifact is stale.")
    gate.status = "approved"
    gate.approval = approval_request
    gate.approved_by = owner
    gate.approved_at = timezone.now()
    gate.save(update_fields=["status", "approval", "approved_by", "approved_at", "updated_at"])
    return gate


def assert_activation_allowed(product):
    if not isinstance(product.metadata, dict) or not product.metadata.get("factory_state"):
        return
    invalidate_stale_evidence(product)
    try:
        gate = product.factory_release_gate
    except FactoryReleaseGate.DoesNotExist:
        gate = None
    if not gate or gate.status != "approved" or not gate.approval_id or not gate.approved_by_id or not gate.approved_by.is_superuser:
        raise ValidationError("Product Factory activation is blocked by the shared owner Release Gate.")
    if gate.approval.status != "approved":
        raise ValidationError("The linked owner ApprovalRequest is not approved.")
    if not gate.approved_at or gate.artifact.version != gate.run.current_artifact_version:
        raise ValidationError("Owner approval does not cover the current artifact version.")
