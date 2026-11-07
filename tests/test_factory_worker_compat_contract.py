"""No-dependency regression for the isolated VPS Factory worker repair."""

import ast
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


def extract_class():
    path = ROOT / "core/factory_worker_compat.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef)
               and node.name == "FactoryWorkerCompatibility")
    namespace = {
        "FactoryWorkerCompatibilityError": type("FactoryWorkerCompatibilityError", (ValueError,), {}),
        "Decimal": Decimal, "InvalidOperation": InvalidOperation,
        "timezone": SimpleNamespace(now=lambda: datetime.now(timezone.utc)),
        "os": SimpleNamespace(environ={"MOJ_FACTORY_SINGLE_ACTIVE_RUN_ID": "run-3"}),
        "json": json, "Path": Path,
    }
    exec(compile(ast.Module(body=[cls], type_ignores=[]), str(path), "exec"), namespace)
    return namespace["FactoryWorkerCompatibility"], namespace["FactoryWorkerCompatibilityError"]


class FactoryWorkerCompatibilityTests(unittest.TestCase):
    def _native_slot(self, worker, active=None):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        slot = Path(directory.name) / "current.json"
        slot.write_text(json.dumps({
            "schema": "saeit.factory.product-slots.v1",
            "active": [{"recipe": "farm_enterprise_economics"}] if active is None else active,
        }), encoding="utf-8")
        worker.NATIVE_SLOT_PATH = slot
        return slot

    def test_only_existing_validation_is_accepted(self):
        worker, error = extract_class()
        self._native_slot(worker)
        base = dict(
            status="queued", capability_code="product_validation",
            attempt_count=0, max_attempts=3, next_retry_at=None,
            factory_run_id=2, product_id=3, environment="production",
            factory_run=SimpleNamespace(status="active", product_id=3, environment="production", run_id="run-3"),
            product=SimpleNamespace(metadata={"recipe": "farm_enterprise_economics"}),
        )
        worker._preflight(SimpleNamespace(**base, action_type="product_validation"))
        binding = worker._preflight.__globals__["os"].environ
        binding.clear()
        with self.assertRaises(error):
            worker._preflight(SimpleNamespace(**base, action_type="product_validation"))
        binding["MOJ_FACTORY_SINGLE_ACTIVE_RUN_ID"] = "run-3"
        with self.assertRaises(error):
            worker._preflight(SimpleNamespace(**base, action_type="product_research"))
        with self.assertRaises(error):
            worker._preflight(SimpleNamespace(**{**base, "product_id": None},
                                              action_type="product_validation"))
        with self.assertRaises(error):
            worker._preflight(SimpleNamespace(**{**base, "factory_run":SimpleNamespace(
                status="active", product_id=4, environment="production", run_id="run-3")},
                action_type="product_validation"))

    def test_binding_rejects_legacy_product_without_proven_recipe(self):
        worker, error = extract_class()
        self._native_slot(worker)
        task = SimpleNamespace(
            status="queued", action_type="product_validation",
            capability_code="product_validation", attempt_count=0, max_attempts=3,
            next_retry_at=None, factory_run_id=2, product_id=3,
            environment="production", factory_run=SimpleNamespace(
                status="active", product_id=3, environment="production", run_id="run-3"
            ), product=SimpleNamespace(metadata={"title": "farm_enterprise_economics"}),
        )
        with self.assertRaisesRegex(error, "not proven"):
            worker._preflight(task)
        task.product.metadata = {"factory": {"recipe": "farm_enterprise_economics"}}
        worker._preflight(task)

    def test_optional_retry_column_can_be_missing_from_legacy_task(self):
        worker, error = extract_class()
        self._native_slot(worker)
        # Source AgentTask lacks next_retry_at; its absence must not produce
        # AttributeError or weaken the mandatory product/run binding.
        task = SimpleNamespace(
            status="queued", action_type="product_validation",
            capability_code="product_validation", attempt_count=0,
            max_attempts=3, factory_run_id=2, product_id=3,
            environment="production", factory_run=SimpleNamespace(
                status="active", product_id=3, environment="production", run_id="run-3"
            ), product=SimpleNamespace(metadata={"recipe": "farm_enterprise_economics"}),
        )
        worker._preflight(task)
        task.next_retry_at = datetime.now(timezone.utc) + timedelta(minutes=5)
        with self.assertRaisesRegex(error, "retry backoff is not due"):
            worker._preflight(task)

    def test_missing_runtime_binding_fails_closed_before_claim(self):
        worker, error = extract_class()
        task = SimpleNamespace(
            status="queued", action_type="product_validation",
            capability_code="product_validation", attempt_count=0, max_attempts=3,
        )
        with self.assertRaisesRegex(error, "schema lacks required run/product binding"):
            worker._preflight(task)

    def test_binding_rejects_unsafe_or_multiple_native_slots(self):
        worker, error = extract_class()
        slot = self._native_slot(worker, active=[
            {"recipe": "farm_enterprise_economics"}, {"recipe": "another_product"}
        ])
        task = SimpleNamespace(product=SimpleNamespace(
            metadata={"recipe": "farm_enterprise_economics"}
        ))
        with self.assertRaisesRegex(error, "does not match"):
            worker._verify_native_product_binding(task)
        slot.unlink()
        with self.assertRaisesRegex(error, "missing or unsafe"):
            worker._verify_native_product_binding(task)

    def test_cost_must_really_be_zero(self):
        worker, error = extract_class()
        self.assertEqual(worker._normalize_result({"verified_effect": True})[1], Decimal("0"))
        for value in ("0.01", "-1", "NaN", "not-number"):
            with self.subTest(value=value), self.assertRaises(error):
                worker._normalize_result({"__cost": value})

    def test_atomic_receipt_and_verifier_are_present(self):
        source = (ROOT / "core/factory_worker_compat.py").read_text(encoding="utf-8")
        self.assertIn("consume_factory_attestation(result.attestation, task)", source)
        self.assertIn("FactoryTaskVerifier().verify(task, output)", source)
        self.assertIn("with transaction.atomic():", source)
        self.assertIn("self.runtime.complete(", source)
        self.assertNotIn("WorkerRunner(", source)
        self.assertIn("self._verify_native_product_binding(task)", source)

    def test_entrypoint_never_consumes_oldest_queued_unscoped(self):
        source = (ROOT / "core/management/commands/factory_product_step.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        self.assertIn('if not task_id:', source)
        self.assertIn('FACTORY_WAIT explicit_task_id_required', source)
        self.assertNotIn('order_by("created_at")', source)
        self.assertNotIn('plan_product_factory_step(', source)
        self.assertIsInstance(tree, ast.Module)


if __name__ == "__main__":
    unittest.main()
