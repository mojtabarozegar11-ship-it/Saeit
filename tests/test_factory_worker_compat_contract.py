"""No-dependency regression for the isolated VPS Factory worker repair."""

import ast
from decimal import Decimal, InvalidOperation
from pathlib import Path
from types import SimpleNamespace
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
        "timezone": SimpleNamespace(now=lambda: None),
    }
    exec(compile(ast.Module(body=[cls], type_ignores=[]), str(path), "exec"), namespace)
    return namespace["FactoryWorkerCompatibility"], namespace["FactoryWorkerCompatibilityError"]


class FactoryWorkerCompatibilityTests(unittest.TestCase):
    def test_only_existing_validation_is_accepted(self):
        worker, error = extract_class()
        base = dict(
            status="queued", capability_code="product_validation",
            attempt_count=0, max_attempts=3, next_retry_at=None,
            factory_run_id=2, product_id=3, environment="production",
            factory_run=SimpleNamespace(status="active", product_id=3, environment="production"),
        )
        worker._preflight(SimpleNamespace(**base, action_type="product_validation"))
        with self.assertRaises(error):
            worker._preflight(SimpleNamespace(**base, action_type="product_research"))
        with self.assertRaises(error):
            worker._preflight(SimpleNamespace(**{**base, "product_id": None},
                                              action_type="product_validation"))
        with self.assertRaises(error):
            worker._preflight(SimpleNamespace(**{**base, "factory_run":SimpleNamespace(
                status="active", product_id=4, environment="production")},
                action_type="product_validation"))

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
