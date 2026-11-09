"""Exercise the Django-facing funnel adapter with an isolated ORM double."""

from datetime import datetime, timezone
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch


class FakeFunnelManager:
    def __init__(self, events):
        self.events = events
        self.filters = []

    def filter(self, **filters):
        self.filters.append(filters)
        return self

    def values(self, *fields):
        assert fields == ("event_name",)
        return self

    def annotate(self, **aggregation):
        assert "total" in aggregation
        return [{"event_name": name, "total": count}
                for name, count in self.events.items()]


class FakeProductManager:
    def __init__(self, count):
        self.quantity = count
        self.filters = []

    def filter(self, **filters):
        self.filters.append(filters)
        return self

    def count(self):
        return self.quantity


def load_tool(events, offers):
    # Import only this adapter while mocking its Django-only dependencies.
    django = types.ModuleType("django")
    utils = types.ModuleType("django.utils")
    orm = types.ModuleType("django.db")
    orm_models = types.ModuleType("django.db.models")
    orm_models.Count = lambda field: ("count", field)
    utils.timezone = types.SimpleNamespace(now=lambda: datetime(2026, 11, 9, tzinfo=timezone.utc))
    models = types.ModuleType("core.models")
    funnel = FakeFunnelManager(events)
    products = FakeProductManager(offers)
    models.AgentTask = object()
    models.Product = types.SimpleNamespace(objects=products)
    models.CommerceFunnelEvent = types.SimpleNamespace(objects=funnel)
    substitutes = {
        "django": django,
        "django.utils": utils,
        "django.db": orm,
        "django.db.models": orm_models,
        "core.models": models,
    }
    for name, attr in (
        ("core.factory_native_review_gateway", "inspect_family"),
        ("core.factory_f41_gateway", "build_verified_order"),
        ("core.production_gate", "ProductionGate"),
    ):
        mod = types.ModuleType(name)
        setattr(mod, attr, lambda *args, **kwargs: None)
        substitutes[name] = mod
    gateway = types.ModuleType("core.tool_gateway")
    gateway.ToolGateway = lambda tools: tools
    gateway.ToolSpec = lambda **kwargs: kwargs
    substitutes["core.tool_gateway"] = gateway
    module_name = "economic_tool_pack_isolated_test"
    module = types.ModuleType(module_name)
    path = Path(__file__).resolve().parents[1] / "core" / "economic_tool_pack.py"
    spec = importlib.util.spec_from_file_location(module_name, path)
    module.__package__ = "core"
    module.__spec__ = spec
    with patch.dict(sys.modules, {**substitutes, module_name: module}):
        spec.loader.exec_module(module)
        result = module.funnel_audit({})
        tools = module.build_economic_gateway()
    return result, tools, funnel, products


class EconomicFunnelToolTests(unittest.TestCase):
    def test_real_orm_aggregate_selects_delivery_breakage(self):
        result, tools, funnel, products = load_tool({
            "delivery_failure": 4, "begin_checkout": 9,
        }, offers=2)
        self.assertEqual(result["next_action"], "inspect_delivery_failures")
        self.assertTrue(result["verified_effect"])
        self.assertIsNone(result["verified_revenue"])
        self.assertEqual(result["revenue_status"], "external_reconciliation_required")
        self.assertEqual(products.filters, [{"active": True, "price__gt": 0}])
        self.assertEqual(len(funnel.filters), 1)
        self.assertIn("income_funnel_audit", [tool["code"] for tool in tools])

    def test_payment_event_never_becomes_collected_income(self):
        result, _, _, _ = load_tool({"payment_confirmed": 15}, offers=3)
        self.assertEqual(result["next_action"], "inspect_payment_to_delivery_path")
        self.assertIsNone(result["verified_revenue"])


if __name__ == "__main__":
    unittest.main()
