"""Isolated adapter for the existing VPS Product Factory worker ABI.

This module deliberately does not alter the economic master's WorkerRunner or
TaskRuntime. It only restores the receipt-bearing path for historical factory
tasks whose ToolGateway and FactoryAgentRuntime are still installed on VPS.
"""

from decimal import Decimal, InvalidOperation
import json
import os
from pathlib import Path

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
    NATIVE_RECIPE = "farm_enterprise_economics"
    NATIVE_SLOT_SCHEMA = "saeit.factory.product-slots.v1"
    NATIVE_SLOT_PATH = Path(
        "/home/githubops/factory-runtime/private/autonomous-product-cycle/"
        "quality-excellence/product-flow/active-slots/current.json"
    )

    def __init__(self, gateway, factory_executor):
        if factory_executor is None:
            raise FactoryWorkerCompatibilityError("Registered FactoryAgentRuntime is required")
        self.gateway = gateway
        self.factory_executor = factory_executor
        self.runtime = TaskRuntime()

    @staticmethod
    def _require_runtime_schema():
        # Validate before select_related(), which otherwise raises a raw
        # FieldError if the source AgentTask lacks VPS-only factory relations.
        fields = {field.name for field in AgentTask._meta.get_fields()}
        if not {"factory_run", "product", "environment"}.issubset(fields):
            raise FactoryWorkerCompatibilityError(
                "Factory AgentTask model lacks run/product/environment relations; "
                "reconcile source and runtime before execution"
            )

    @classmethod
    def _verify_native_product_binding(cls, task):
        # The Django FactoryRun table has hundreds of historical "active" rows.
        # An operator-supplied run ID must not override the native VPS factory's
        # single-product lock. Require exact Product metadata, not a title or
        # other human-readable string that could describe a different product.
        metadata = task.product.metadata if task.product is not None else None
        if not isinstance(metadata, dict):
            raise FactoryWorkerCompatibilityError("Existing Product lacks explicit recipe metadata")
        recipe = cls.NATIVE_RECIPE
        matches = any(metadata.get(key) == recipe for key in (
            "recipe", "recipe_slug", "product_slug", "product_code", "sku"
        ))
        for container in ("factory", "production", "source_recipe"):
            value = metadata.get(container)
            if isinstance(value, dict):
                matches |= any(value.get(key) == recipe for key in (
                    "recipe", "recipe_slug", "product_slug"
                ))
            elif container == "source_recipe" and value == recipe:
                matches = True
        if not matches:
            raise FactoryWorkerCompatibilityError("Product is not proven to be the native active recipe")

        slot = cls.NATIVE_SLOT_PATH
        try:
            safe_slot = not slot.is_symlink() and slot.is_file() and slot.stat().st_size < 2000000
        except OSError:
            safe_slot = False
        if not safe_slot:
            raise FactoryWorkerCompatibilityError("Native factory active slot is missing or unsafe")
        try:
            data = json.loads(slot.read_text(encoding="utf-8"))
        except (OSError, ValueError, UnicodeError, TypeError) as exc:
            raise FactoryWorkerCompatibilityError("Native factory active slot is unreadable") from exc
        if (not isinstance(data, dict)
                or data.get("schema") != cls.NATIVE_SLOT_SCHEMA
                or not isinstance(data.get("active"), list)
                or len(data["active"]) != 1
                or not isinstance(data["active"][0], dict)
                or data["active"][0].get("recipe") != recipe):
            raise FactoryWorkerCompatibilityError("Native factory active slot does not match the product")

    @classmethod
    def _preflight(cls, task):
        if task.action_type not in cls.ALLOWED_ACTIONS:
            raise FactoryWorkerCompatibilityError("Factory action is not reconciled for this worker")
        if task.action_type != task.capability_code:
            raise FactoryWorkerCompatibilityError("Factory task and capability mismatch")
        if task.status != "queued":
            raise FactoryWorkerCompatibilityError("Factory task is not queued")
        if task.attempt_count >= task.max_attempts:
            raise FactoryWorkerCompatibilityError("Factory task retry budget is exhausted")
        # The checked-in AgentTask model and some VPS-local factory schemas
        # differ. Never let a missing relation crash after a task is claimed,
        # or treat source-only fields as evidence of a verified factory run.
        required_binding_fields = (
            "factory_run_id", "product_id", "factory_run", "product", "environment"
        )
        if any(not hasattr(task, field) for field in required_binding_fields):
            raise FactoryWorkerCompatibilityError(
                "Factory task schema lacks required run/product binding; reconcile runtime first"
            )
        # A retry timestamp is optional in the legacy AgentTask schema. When
        # present, retain its backoff gate; retries remain attempt-bounded.
        retry_at = getattr(task, "next_retry_at", None)
        if retry_at is not None and retry_at > timezone.now():
            raise FactoryWorkerCompatibilityError("Factory task retry backoff is not due")
        if not task.factory_run_id or not task.product_id:
            raise FactoryWorkerCompatibilityError("Factory task has no existing Product and Run")
        if task.factory_run.status != "active" or task.factory_run.product_id != task.product_id:
            raise FactoryWorkerCompatibilityError("Factory task has an inactive or mismatched Run")
        if task.factory_run.environment != task.environment:
            raise FactoryWorkerCompatibilityError("Factory task environment differs from its Run")
        # The historical database contains hundreds of active FactoryRun rows,
        # whereas the owner permits only one genuine factory product at a time.
        # Never infer the selected run from those stale status flags. An explicit
        # operations binding is mandatory before any validation can be claimed.
        bound_run = os.environ.get("MOJ_FACTORY_SINGLE_ACTIVE_RUN_ID", "").strip()
        if not bound_run or task.factory_run.run_id != bound_run:
            raise FactoryWorkerCompatibilityError("No verified single active FactoryRun binding")
        cls._verify_native_product_binding(task)

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
        cls._verify_native_product_binding(task)
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
        self._require_runtime_schema()
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
                self._verify_native_product_binding(task)
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
