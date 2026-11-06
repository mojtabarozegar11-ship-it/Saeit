"""Isolated adapter for the existing VPS Product Factory worker ABI.

This module deliberately does not alter the economic master's WorkerRunner or
TaskRuntime. It only restores the receipt-bearing path for historical factory
tasks whose ToolGateway and FactoryAgentRuntime are still installed on VPS.
"""

from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone

from .factory_contracts import GatewayToolResult
from .factory_governance import FactoryTaskVerifier
from .models import AgentTask, Product
from .task_runtime import TaskExecutionError, TaskRuntime
from .tool_gateway import consume_factory_attestation


class FactoryWorkerCompatibilityError(ValueError):
    pass


class FactoryWorkerCompatibility:
    """One explicitly selected existing task, never a newly-created product."""

    # Research without a Product would create another independent product.
    # The owner requires a single active factory product, so leave those tasks
    # queued pending a separately verified product/run reconciliation.
    ALLOWED_ACTIONS = frozenset({"product_validation"})
    ALLOWED_VALIDATION_STATES = frozenset({
        "validated", "needs_research", "rejected", "blocked"
    })
    ALLOWED_VALIDATION_OUTCOMES = frozenset({
        "VALIDATED", "NEEDS_MORE_EVIDENCE", "RESEARCH_AGAIN", "REJECTED", "BLOCKED"
    })

    def __init__(self, gateway, factory_executor):
        if factory_executor is None:
            raise FactoryWorkerCompatibilityError("Registered FactoryAgentRuntime is required")
        self.gateway = gateway
        self.factory_executor = factory_executor
        self.runtime = TaskRuntime()

    @staticmethod
    def _preflight(task):
        if task.action_type not in FactoryWorkerCompatibility.ALLOWED_ACTIONS:
            raise FactoryWorkerCompatibilityError("Factory action is not reconciled for this worker")
        if task.action_type != task.capability_code:
            raise FactoryWorkerCompatibilityError("Factory task and capability mismatch")
        if task.status != "queued":
            raise FactoryWorkerCompatibilityError("Factory task is not queued")
        if task.attempt_count >= task.max_attempts:
            raise FactoryWorkerCompatibilityError("Factory task retry budget is exhausted")
        if task.next_retry_at and task.next_retry_at > timezone.now():
            raise FactoryWorkerCompatibilityError("Factory task retry backoff is not due")
        if not task.factory_run_id or not task.product_id:
            raise FactoryWorkerCompatibilityError("Factory task has no existing Product and Run")
        if task.factory_run.status != "active" or task.factory_run.product_id != task.product_id:
            raise FactoryWorkerCompatibilityError("Factory task has an inactive or mismatched Run")
        if task.factory_run.environment != task.environment:
            raise FactoryWorkerCompatibilityError("Factory task environment differs from its Run")

    @staticmethod
    def _normalize_result(result):
        if not isinstance(result, dict):
            raise FactoryWorkerCompatibilityError("Factory tool must return an evidence object")
        data = dict(result)
        try:
            cost = Decimal(str(data.pop("__cost", "0")))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise FactoryWorkerCompatibilityError("Factory cost is invalid") from exc
        if not cost.is_finite() or cost != 0:
            raise FactoryWorkerCompatibilityError("Factory task requires zero financial cost")
        return data, cost

    @classmethod
    def _verify_validation_effect(cls, task, output):
        if output.get("verified_effect") is not True:
            raise FactoryWorkerCompatibilityError("Factory validation has no verified effect")
        if output.get("product_id") != task.product_id:
            raise FactoryWorkerCompatibilityError("Factory validation output Product mismatch")
        product = Product.objects.select_for_update().get(pk=task.product_id)
        metadata = product.metadata if isinstance(product.metadata, dict) else {}
        state = metadata.get("factory_state")
        if state not in cls.ALLOWED_VALIDATION_STATES or output.get("factory_state") != state:
            raise FactoryWorkerCompatibilityError("Persisted validation state differs from the result")
        persisted = metadata.get("validation") or {}
        outcome = (output.get("validation") or {}).get("outcome")
        if (not isinstance(persisted, dict) or not persisted.get("policy_version")
                or persisted.get("outcome") != outcome
                or outcome not in cls.ALLOWED_VALIDATION_OUTCOMES):
            raise FactoryWorkerCompatibilityError("Typed validation outcome is not persisted")
        FactoryTaskVerifier().verify(task, output)
        return product, metadata

    def run(self, task_id):
        # Preflight is outside claim and never consumes an attempt for an
        # orphaned task. The same checks are repeated while holding locks.
        task = AgentTask.objects.select_related("factory_run", "product").get(pk=task_id)
        self._preflight(task)
        with transaction.atomic():
            locked = AgentTask.objects.select_for_update().select_related(
                "factory_run", "product"
            ).get(pk=task_id)
            self._preflight(locked)
            task = self.runtime.claim(task_id)
            execution_id = task.execution_id

        try:
            self.runtime.heartbeat(task.pk, execution_id=execution_id)
            with transaction.atomic():
                payload = task.input_data or {}
                if not isinstance(payload, dict):
                    raise FactoryWorkerCompatibilityError("Factory task input must be an object")
                authorization = self.gateway.authorize(
                    task.action_type, payload, task_id=task.pk, execution_id=execution_id
                )
                adapter_receipt = self.gateway.execute_factory_adapter(
                    self.factory_executor, task, authorization
                )
                result = self.gateway.invoke(
                    task.action_type, payload, task_id=task.pk,
                    execution_id=execution_id, adapter_receipt=adapter_receipt,
                )
                if not isinstance(result, GatewayToolResult):
                    raise FactoryWorkerCompatibilityError("Factory ToolGateway attestation missing")
                output, cost = self._normalize_result(result.result)
                self._verify_validation_effect(task, output)
                consume_factory_attestation(result.attestation, task)
                done = self.runtime.complete(
                    task.pk, output_data=output, cost=cost, execution_id=execution_id
                )
                # Recorded only after the output and underlying ToolGateway
                # effect have been verified in the same transaction.
                product = Product.objects.select_for_update().get(pk=task.product_id)
                metadata = product.metadata if isinstance(product.metadata, dict) else {}
                history = list(metadata.get("factory_history") or [])
                history.append({
                    "task_id": task.pk, "action": task.action_type,
                    "state": metadata.get("factory_state"),
                    "execution_id": execution_id, "verified_at": timezone.now().isoformat(),
                })
                product.metadata = {**metadata, "factory_history": history}
                product.save(update_fields=["metadata", "updated_at"])
            return done
        except Exception as exc:
            try:
                self.runtime.fail(task.pk, str(exc)[:5000], execution_id=execution_id)
            except TaskExecutionError:
                pass
            raise
