"""Dependency-free checks for the real master-agent profit baseline handler.

Extract the actual function from source so neither Django nor a database is
imported or modified by this read-only regression suite.
"""

import ast
from pathlib import Path
from types import SimpleNamespace
import unittest


SOURCE = Path(__file__).resolve().parents[1] / "core" / "economic_tool_pack.py"
MASTER_LOOP = (Path(__file__).resolve().parents[1] / "core" / "management" /
               "commands" / "autonomous_master_loop.py")
ECONOMIC_WORKER = (Path(__file__).resolve().parents[1] / "core" / "management" /
                   "commands" / "run_economic_worker.py")


class _QuerySet:
    def __init__(self, products):
        self.products = products

    def count(self):
        return len(self.products)

    def values(self, *fields):
        return [{field: product[field] for field in fields} for product in self.products]


class _Objects:
    def __init__(self, products):
        self.products = products
        self.filters = []

    def filter(self, **kwargs):
        self.filters.append(kwargs)
        return _QuerySet(self.products)


def _invoke(products):
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"), filename=str(SOURCE))
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name == "profit_optimize"]
    assert len(functions) == 1
    module = ast.Module(body=functions, type_ignores=[])
    objects = _Objects(products)
    product_stub = type("Product", (), {"objects": objects})
    globals_for_function = {
        "Product": product_stub,
        "_evidence": lambda kind, value: {"kind": kind, "value": value},
    }
    exec(compile(module, str(SOURCE), "exec"), globals_for_function)
    return globals_for_function["profit_optimize"]({}), objects.filters


def _product(number):
    return {"id": number, "title": f"Product {number}",
            "price": 0, "currency": "USD"}


def _run_master_loop_with_result(progress_class, *, max_steps=20):
    """Exercise the actual loop body with no Django imports or database."""
    tree = ast.parse(MASTER_LOOP.read_text(encoding="utf-8"), filename=str(MASTER_LOOP))
    commands = [node for node in tree.body if isinstance(node, ast.ClassDef)
                and node.name == "Command"]
    assert len(commands) == 1
    module = ast.Module(body=commands, type_ignores=[])
    runs = []
    messages = []
    task = SimpleNamespace(pk=42, action_type="income_profit_optimize")
    task.output_data = {"verified_effect": True, "progress_class": progress_class}
    task.refresh_from_db = lambda: None
    class _Runner:
        def __init__(self, gateway):
            pass

        def run(self, task_id):
            runs.append(task_id)
            return task

    namespace = {
        "BaseCommand": object,
        "AutonomousBrain": lambda: object(),
        "build_economic_gateway": lambda: SimpleNamespace(
            describe=lambda: {"income_profit_optimize": {"enabled": True}}),
        "WorkerRunner": _Runner,
        "call_command": lambda *args: (_ for _ in ()).throw(
            AssertionError("An existing task must not trigger planning")),
    }
    exec(compile(module, str(MASTER_LOOP), "exec"), namespace)
    command = namespace["Command"]()
    command.stdout = SimpleNamespace(write=messages.append)
    command.style = SimpleNamespace(SUCCESS=lambda message: message)
    command._next_eligible_task = lambda supported: task
    command.handle(max_steps=max_steps)
    return runs, messages


def _run_worker_drain_with_result(progress_class):
    tree = ast.parse(ECONOMIC_WORKER.read_text(encoding="utf-8"),
                     filename=str(ECONOMIC_WORKER))
    commands = [node for node in tree.body if isinstance(node, ast.ClassDef)
                and node.name == "Command"]
    assert len(commands) == 1
    module = ast.Module(body=commands, type_ignores=[])
    runs = []
    messages = []
    task = SimpleNamespace(pk=42, action_type="income_profit_optimize")
    completed = SimpleNamespace(pk=42, status="completed", output_data={
        "verified_effect": True, "progress_class": progress_class,
    })

    class _Queue:
        def exclude(self, **kwargs):
            return self

        def order_by(self, *args):
            return self

        def first(self):
            return task

    class _Runner:
        def __init__(self, gateway):
            pass

        def run(self, task_id):
            runs.append(task_id)
            return completed

    namespace = {
        "BaseCommand": object,
        "CommandError": ValueError,
        "F": lambda name: name,
        "AgentTask": SimpleNamespace(objects=SimpleNamespace(
            filter=lambda **kwargs: _Queue())),
        "build_economic_gateway": lambda: SimpleNamespace(
            describe=lambda: {"income_profit_optimize": {"enabled": True}}),
        "WorkerRunner": _Runner,
    }
    exec(compile(module, str(ECONOMIC_WORKER), "exec"), namespace)
    command = namespace["Command"]()
    command.stdout = SimpleNamespace(write=messages.append)
    command.style = SimpleNamespace(SUCCESS=lambda message: message)
    command.handle(drain=True, limit=1, task_id=None)
    return runs, messages


class ProfitEvidenceContractTest(unittest.TestCase):
    def test_empty_catalog_cannot_claim_profit_or_revenue(self):
        result, filters = _invoke([])
        self.assertEqual(filters, [{"active": True}])
        self.assertTrue(result["verified_effect"])
        self.assertTrue(result["inspection_completed"])
        self.assertEqual(result["progress_class"], "diagnostic_only")
        self.assertFalse(result["business_outcome_verified"])
        self.assertIsNone(result["verified_profit"])
        self.assertIsNone(result["verified_revenue"])
        self.assertEqual(result["next_action"], "await_active_product")
        self.assertEqual(result["evidence"]["value"]["active_products"], 0)

    def test_one_active_product_still_requires_external_profit_evidence(self):
        result, filters = _invoke([_product(1)])
        self.assertEqual(filters, [{"active": True}])
        self.assertTrue(result["verified_effect"])
        self.assertEqual(result["progress_class"], "diagnostic_only")
        self.assertEqual(result["next_action"], "await_external_profit_evidence")
        self.assertEqual(result["evidence"]["kind"], "profit_baseline")
        self.assertEqual(result["evidence"]["value"]["active_products"], 1)
        self.assertFalse(result["evidence"]["value"]["sample_truncated"])

    def test_catalog_sample_is_bounded_without_undercounting(self):
        result, filters = _invoke([_product(n) for n in range(120)])
        self.assertEqual(filters, [{"active": True}])
        self.assertTrue(result["verified_effect"])
        evidence = result["evidence"]["value"]
        self.assertEqual(evidence["active_products"], 120)
        self.assertEqual(evidence["sampled_products"], 100)
        self.assertEqual(len(evidence["products"]), 100)
        self.assertTrue(evidence["sample_truncated"])

    def test_master_loop_stops_after_diagnostic_even_with_twenty_step_budget(self):
        runs, messages = _run_master_loop_with_result("diagnostic_only")
        self.assertEqual(runs, [42])
        self.assertTrue(any("AUTO_DIAGNOSTIC_BOUNDARY" in message
                            for message in messages))

    def test_master_loop_does_not_stop_other_verified_work_on_diagnostic_gate(self):
        runs, messages = _run_master_loop_with_result("real_operation", max_steps=2)
        self.assertEqual(runs, [42, 42])
        self.assertFalse(any("AUTO_DIAGNOSTIC_BOUNDARY" in message
                             for message in messages))

    def test_drain_stops_after_one_diagnostic_task(self):
        runs, messages = _run_worker_drain_with_result("diagnostic_only")
        self.assertEqual(runs, [42])
        self.assertTrue(any("DRAIN_DIAGNOSTIC_BOUNDARY" in message
                            for message in messages))
        self.assertIn("DRAIN_SUMMARY completed=1 limit=20", messages)

    def test_drain_retains_bounded_behavior_for_real_operations(self):
        runs, messages = _run_worker_drain_with_result("real_operation")
        self.assertEqual(len(runs), 20)
        self.assertIn("DRAIN_SUMMARY completed=20 limit=20", messages)


if __name__ == "__main__":
    unittest.main()
