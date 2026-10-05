from decimal import Decimal, InvalidOperation
import uuid

from django.db import transaction
from django.utils import timezone
from datetime import timedelta

from .agent_registry import AgentRegistry
from .factory_governance import FactoryTaskVerifier
from .models import AgentTask, ApprovalRequest, AuditLog, FactoryMarketEligibility, Product
from .services import normalize_risk, requires_owner_approval


TERMINAL_STATUSES = frozenset({"completed", "failed", "cancelled"})


class TaskExecutionError(ValueError):
    """Raised when a task cannot safely enter execution."""


class TaskRuntime:
    """Controlled AgentTask lifecycle with final policy, identity, and retry gates."""

    @transaction.atomic
    def claim(self, task_id):
        task = AgentTask.objects.select_for_update().select_related("agent").get(pk=task_id)
        if task.status != "queued":
            if task.status == "failed" and task.attempt_count >= task.max_attempts:
                raise TaskExecutionError("Task retry budget exhausted")
            raise TaskExecutionError(f"Task is not executable from status: {task.status}")
        if task.next_retry_at and task.next_retry_at > timezone.now():
            raise TaskExecutionError("Task retry backoff has not elapsed")
        if not task.agent.active:
            raise TaskExecutionError("Task agent is inactive")

        registry = AgentRegistry()
        capability = registry.capability_for(task.agent, task.action_type)
        if not capability:
            raise TaskExecutionError("Task agent no longer has an active capability for this action")
        if task.capability_code and capability.code != task.capability_code:
            raise TaskExecutionError("Task capability policy no longer matches its execution snapshot")

        try:
            snapshot_risk = normalize_risk(task.risk_snapshot)
        except ValueError as exc:
            raise TaskExecutionError("Task risk snapshot is invalid") from exc
        effective_risk = registry.effective_risk(capability, snapshot_risk)
        if effective_risk != snapshot_risk:
            raise TaskExecutionError("Task risk policy has changed since planning; owner approval is required before execution")
        if requires_owner_approval(task.action_type, effective_risk):
            approved = ApprovalRequest.objects.filter(
                target_type="AgentTask", target_id=str(task.pk), status="approved"
            ).exists()
            if not approved:
                raise TaskExecutionError("Owner approval is required before execution")

        if task.attempt_count >= task.max_attempts:
            raise TaskExecutionError("Task retry budget exhausted")
        task.execution_id = uuid.uuid4().hex
        task.attempt_count += 1
        task.status = "running"
        task.save(update_fields=["execution_id", "attempt_count", "status", "updated_at"])
        self._audit(task, "task_claimed", {
            "status": "running",
            "action_type": task.action_type,
            "risk": effective_risk,
            "execution_id": task.execution_id,
            "attempt": task.attempt_count,
        })
        return task

    @transaction.atomic
    def heartbeat(self, task_id, execution_id=None):
        task = AgentTask.objects.select_for_update().get(pk=task_id)
        if task.status != "running":
            raise TaskExecutionError(f"Task is not running: {task.status}")
        if not execution_id or execution_id != task.execution_id:
            raise TaskExecutionError(
                "Execution identity does not match the active task execution"
            )
        task.save(update_fields=["updated_at"])
        return task

    @transaction.atomic
    def recover_stale(self, task_id, stale_after_seconds=900):
        try:
            seconds = int(stale_after_seconds)
        except (TypeError, ValueError) as exc:
            raise TaskExecutionError("stale_after_seconds must be an integer") from exc
        if seconds <= 0:
            raise TaskExecutionError("stale_after_seconds must be positive")

        task = AgentTask.objects.select_for_update().select_related("agent").get(pk=task_id)
        if task.status != "running":
            raise TaskExecutionError(f"Task is not running: {task.status}")

        cutoff = timezone.now() - timedelta(seconds=seconds)
        if task.updated_at > cutoff:
            raise TaskExecutionError("Task execution is not stale")

        previous_execution_id = task.execution_id
        if task.attempt_count >= task.max_attempts:
            task.status = "failed"
            task.next_retry_at = None
            task.output_data = {"error": "Execution became stale and retry budget was exhausted"}
        else:
            task.status = "queued"
            task.execution_id = ""
            task.next_retry_at = timezone.now() + timedelta(seconds=min(30 * (2 ** max(task.attempt_count - 1, 0)), 300)) if (
                str(task.capability_code or "").startswith("product_")
                or str(task.action_type or "").startswith("product_")
            ) else None
            task.output_data = {"error": "Execution became stale and was re-queued for recovery"}
            if task.next_retry_at:
                task.output_data["retry_after"] = task.next_retry_at.isoformat()
        task.save(update_fields=["status", "execution_id", "next_retry_at", "output_data", "updated_at"])
        self._audit(
            task,
            "task_recovered_stale",
            {
                "status": task.status,
                "previous_execution_id": previous_execution_id,
                "attempt": task.attempt_count,
                "stale_after_seconds": seconds,
            },
            trace_execution_id=previous_execution_id,
        )
        return task

    @transaction.atomic
    def complete(self, task_id, output_data=None, cost=0, execution_id=None, gateway_attestation=None):
        task = AgentTask.objects.select_for_update().get(pk=task_id)
        if task.status != "running":
            raise TaskExecutionError(f"Task is not running: {task.status}")
        if not execution_id or execution_id != task.execution_id:
            raise TaskExecutionError("Execution identity does not match the active task execution")
        if not isinstance(output_data or {}, dict):
            raise TaskExecutionError("Task output must be an object")
        try:
            normalized_cost = Decimal(str(cost if cost is not None else "0"))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise TaskExecutionError("Task cost is invalid") from exc
        if not normalized_cost.is_finite():
            raise TaskExecutionError("Task cost must be finite")
        if normalized_cost < 0:
            raise TaskExecutionError("Task cost cannot be negative")
        normalized_output = output_data or {}
        if (
            str(task.capability_code or "").startswith("product_")
            or str(task.action_type or "").startswith("product_")
        ):
            from .tool_gateway import consume_factory_attestation
            try:
                consume_factory_attestation(gateway_attestation, task)
            except Exception as exc:
                raise TaskExecutionError(str(exc)) from exc
            self._verify_factory_effect(task, normalized_output)
            try:
                FactoryTaskVerifier().verify(task, normalized_output)
            except Exception as exc:
                raise TaskExecutionError(str(exc)) from exc
        # Economic work is not complete merely because a handler returned. It must
        # prove an observable effect. This prevents report-only/no-op cycles from
        # being counted as operational progress.
        if str(task.capability_code or "").startswith("income_"):
            if normalized_output.get("verified_effect") is not True:
                raise TaskExecutionError(
                    "Economic task cannot complete without verified_effect=true"
                )
            evidence = normalized_output.get("evidence")
            if not isinstance(evidence, dict) or not any(
                str(value or "").strip() for value in evidence.values()
            ):
                raise TaskExecutionError(
                    "Economic task cannot complete without concrete evidence"
                )
            action = str(normalized_output.get("action_performed") or "").strip()
            if not action:
                raise TaskExecutionError(
                    "Economic task cannot complete without action_performed"
                )
        task.output_data = normalized_output
        task.cost = normalized_cost
        task.status = "completed"
        task.next_retry_at = None
        task.save(update_fields=["output_data", "cost", "status", "next_retry_at", "updated_at"])
        self._audit(task, "task_completed", {"status": "completed", "execution_id": task.execution_id})
        return task

    @staticmethod
    def _verify_factory_effect(task, output):
        """Re-read the product write before accepting an agent's success claim."""
        expected_states = {
            "product_research": "researched",
            "product_opportunity_score": "scored",
            "product_validation": "validated",
            "product_spec": "specified",
            "product_build_record": "built",
            "product_qa": "qa_passed",
            "product_localize": "localized",
            "product_launch_candidate": "launch_candidate",
        }
        expected = expected_states.get(task.action_type)
        if not expected:
            raise TaskExecutionError("Product Factory task has no registered lifecycle verifier")
        if output.get("verified_effect") is not True:
            raise TaskExecutionError("Product Factory task did not report a verifiable effect")
        product_id = output.get("product_id")
        if not product_id:
            raise TaskExecutionError("Product Factory output must identify its Product")
        try:
            product = Product.objects.select_for_update().get(pk=product_id)
        except (Product.DoesNotExist, TypeError, ValueError) as exc:
            raise TaskExecutionError("Product Factory output references no persisted Product") from exc
        metadata = product.metadata if isinstance(product.metadata, dict) else {}
        allowed_states = {expected}
        if task.action_type == "product_validation":
            allowed_states.update({"needs_research", "rejected", "blocked"})
        if metadata.get("factory_state") not in allowed_states or output.get("factory_state") != metadata.get("factory_state"):
            raise TaskExecutionError("Persisted Product lifecycle state does not match task output")
        if task.action_type == "product_validation":
            validation = metadata.get("validation") or {}
            outcome = (output.get("validation") or {}).get("outcome")
            if validation.get("outcome") != outcome or outcome not in {
                "VALIDATED", "NEEDS_MORE_EVIDENCE", "RESEARCH_AGAIN", "REJECTED", "BLOCKED"
            }:
                raise TaskExecutionError("Typed Validation outcome was not persisted")
        if task.action_type == "product_research":
            sources = (metadata.get("research") or {}).get("sources") or []
            if not sources or output.get("evidence_count") != len(sources):
                raise TaskExecutionError("Research completion requires persisted source evidence")
        elif task.action_type == "product_opportunity_score":
            score = (metadata.get("opportunity") or {}).get("score")
            status = (metadata.get("opportunity") or {}).get("status")
            if (score is None and status != "needs_evidence") or (
                score is not None and float(score) != float(output.get("score", -1))
            ):
                raise TaskExecutionError("Opportunity score was not persisted on the Product")
        elif task.action_type == "product_validation":
            if not (metadata.get("validation") or {}).get("policy_version"):
                raise TaskExecutionError("Validation policy/version is missing")
        elif task.action_type == "product_spec" and not (metadata.get("spec") or {}).get("acceptance_criteria"):
            raise TaskExecutionError("Product specification is missing acceptance criteria")
        elif task.action_type == "product_build_record" and not (metadata.get("build") or {}).get("ref"):
            raise TaskExecutionError("Product build has no persisted versioned artifact reference")
        elif task.action_type == "product_qa":
            qa = metadata.get("qa") or {}
            if (qa.get("tests") or {}).get("passed") is not True or (qa.get("security") or {}).get("passed") is not True:
                raise TaskExecutionError("QA and security evidence are not both passing")
        elif task.action_type == "product_localize":
            locales = (metadata.get("localization") or {}).get("launch_locales") or []
            if not locales or locales != output.get("locales"):
                raise TaskExecutionError("Launch locale evidence was not persisted")
        elif task.action_type == "product_launch_candidate":
            markets = metadata.get("market_eligibility") or []
            if product.active or metadata.get("owner_publish_approval_required") is not True:
                raise TaskExecutionError("Launch candidacy must remain inactive and owner-gated")
            reviewed = []
            now = timezone.now()
            for item in markets:
                if not isinstance(item, dict):
                    continue
                record = FactoryMarketEligibility.objects.select_for_update().filter(
                    market_code=item.get("market_code"), reviewed_by__is_superuser=True
                ).select_related("reviewed_by").first()
                if not record or record.eligibility != item.get("eligibility"):
                    raise TaskExecutionError("Market eligibility does not match the owner-reviewed registry")
                if record.valid_until and record.valid_until <= now:
                    raise TaskExecutionError("Market eligibility review expired before task verification")
                if record.eligibility == FactoryMarketEligibility.ALLOWED and (
                    not record.evidence_reference or not record.review_note.strip() or not record.valid_until
                ):
                    raise TaskExecutionError("Allowed market is missing owner review evidence")
                reviewed.append(record)
            if not any(item.eligibility == FactoryMarketEligibility.ALLOWED for item in reviewed):
                raise TaskExecutionError("Launch candidacy requires an allowed market record")

        history = list(metadata.get("factory_history") or [])
        history.append({
            "task_id": task.pk,
            "action": task.action_type,
            "state": expected,
            "execution_id": task.execution_id,
            "verified_at": timezone.now().isoformat(),
        })
        product.metadata = {**metadata, "factory_history": history}
        product.save(update_fields=["metadata", "updated_at"])

    @transaction.atomic
    def fail(self, task_id, error, execution_id=None, retry_backoff=False):
        task = AgentTask.objects.select_for_update().get(pk=task_id)
        if task.status != "running":
            raise TaskExecutionError(f"Task is not running: {task.status}")
        if not execution_id or execution_id != task.execution_id:
            raise TaskExecutionError("Execution identity does not match the active task execution")
        if not str(error or "").strip():
            raise TaskExecutionError("Task failure reason is required")
        previous_execution_id = task.execution_id
        task.output_data = {"error": str(error)[:5000]}
        if getattr(error, "retryable", True) is False:
            task.status, task.execution_id, task.next_retry_at = "blocked", "", None
        elif task.attempt_count >= task.max_attempts:
            task.status, task.next_retry_at = "failed", None
        else:
            task.execution_id = ""
            task.status = "queued"
            task.next_retry_at = (
                timezone.now() + timedelta(seconds=min(30 * (2 ** max(task.attempt_count - 1, 0)), 300))
                if retry_backoff else None
            )
            if task.next_retry_at:
                task.output_data["retry_after"] = task.next_retry_at.isoformat()
        task.save(update_fields=["output_data", "execution_id", "status", "next_retry_at", "updated_at"])
        if task.status == "blocked" and task.factory_run_id:
            run = FactoryRun.objects.select_for_update().get(pk=task.factory_run_id)
            run.status = "blocked"
            run.save(update_fields=["status", "updated_at"])
        self._audit(
            task,
            "task_failed",
            {
                "status": task.status,
                "error": str(error)[:5000],
                "execution_id": task.execution_id,
                "previous_execution_id": previous_execution_id,
                "attempt": task.attempt_count,
            },
            trace_execution_id=previous_execution_id,
        )
        return task

    @transaction.atomic
    def resume_blocked(self, task_id, owner, reason):
        task = AgentTask.objects.select_for_update().get(pk=task_id)
        if task.status != "blocked":
            raise TaskExecutionError("Only a blocked task can be resumed")
        if not owner or not owner.is_superuser:
            raise TaskExecutionError("Owner authority is required to resume blocked work")
        if not str(reason or "").strip():
            raise TaskExecutionError("A remediation reason is required")
        task.status, task.execution_id, task.next_retry_at = "queued", "", None
        task.output_data = {**(task.output_data or {}), "resumed_by": owner.pk, "remediation": str(reason)[:1000]}
        task.save(update_fields=["status", "execution_id", "next_retry_at", "output_data", "updated_at"])
        if task.factory_run_id and task.factory_run.status == "blocked":
            task.factory_run.status = "active"
            task.factory_run.save(update_fields=["status", "updated_at"])
        self._audit(task, "task_resumed_after_remediation", task.output_data)
        return task

    def _audit(self, task, action, state, trace_execution_id=None):
        trace_execution_id = trace_execution_id or task.execution_id or "none"
        AuditLog.objects.create(
            actor_type="agent",
            actor_id=str(task.agent_id),
            action=action,
            target_type="AgentTask",
            target_id=str(task.pk),
            after_state=state,
            trace_id=f"task-{task.pk}-{trace_execution_id}",
        )
