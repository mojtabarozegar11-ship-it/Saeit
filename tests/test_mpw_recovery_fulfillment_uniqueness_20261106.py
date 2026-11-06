"""Offline regression: no paid recovery unless every order item is ready once."""
from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
import unittest


SOURCE = Path(__file__).resolve().parents[1] / "services/mpw_trx_email_recovery.py"


class FulfillmentUniqueness(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tree = ast.parse(SOURCE.read_text("utf-8"))
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                    and n.name == "_ready")
        cls.code = compile(ast.Module(body=[node], type_ignores=[]), str(SOURCE), "exec")

    def ready(self, count, rows, *, model_valid=True):
        item_field = SimpleNamespace(name="item", related_model=SimpleNamespace(
            _meta=SimpleNamespace(label_lower="core.orderitem" if model_valid else "elsewhere")))
        status_field = SimpleNamespace(name="status")

        class FulfillmentQuery:
            def filter(self, **kwargs):
                assert kwargs == {"item__order_id": 91}
                return self

            def values_list(self, *names):
                assert names == ("item_id", "status")
                return rows

        model = SimpleNamespace(
            _meta=SimpleNamespace(fields=[item_field, status_field]),
            objects=FulfillmentQuery(),
        )
        item_query = SimpleNamespace(
            filter=lambda **kwargs: SimpleNamespace(count=lambda: count))
        space = {"apps": SimpleNamespace(get_model=lambda *args: model),
                 "OrderItem": SimpleNamespace(objects=item_query)}
        exec(self.code, space)
        return space["_ready"](SimpleNamespace(pk=91))

    def test_two_distinct_ready_items_pass(self):
        self.assertTrue(self.ready(2, [(11, "ready"), (22, "READY")]))

    def test_missing_one_item_fails(self):
        self.assertFalse(self.ready(2, [(11, "ready")]))

    def test_duplicate_fulfillment_cannot_mask_missing_item(self):
        self.assertFalse(self.ready(2, [(11, "ready"), (11, "ready")]))

    def test_nonready_and_excess_rows_fail(self):
        self.assertFalse(self.ready(2, [(11, "ready"), (22, "failed")]))
        self.assertFalse(self.ready(2, [(11, "ready"), (22, "ready"), (22, "ready")]))

    def test_zero_items_and_wrong_relation_fail_closed(self):
        self.assertFalse(self.ready(0, []))
        self.assertFalse(self.ready(2, [(11, "ready"), (22, "ready")], model_valid=False))


if __name__ == "__main__":
    unittest.main()
