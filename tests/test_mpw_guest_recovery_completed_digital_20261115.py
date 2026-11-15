"""Paid digital re-download remains eligible after first delivery completion.

Pure ORM mocks, no real orders, email, media access, paid invoice or RPC.
The independent finalized payment and guest email ownership checks continue
to run separately on each recovery endpoint and are not bypassed here.
"""
import ast
from pathlib import Path
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

SOURCE = Path(__file__).resolve().parents[1] / "services/mpw_trx_email_recovery.py"
TREE = ast.parse(SOURCE.read_text(encoding="utf-8"))
NODES = [
    n for n in TREE.body if isinstance(n, ast.FunctionDef) and n.name == "_ready"
]
if len(NODES) != 1:
    raise AssertionError("Buyer entitlement helper must exist exactly once")
SCOPE = {}
exec(compile(ast.Module(body=NODES, type_ignores=[]), str(SOURCE), "exec"), SCOPE)


class PurchasedDigitalRecoveryTests(unittest.TestCase):
    def candidate(self, *, count=2, grant_count=2, unique_count=2,
                  include_kind=True):
        OrderItem = Mock()
        OrderItem.objects.filter.return_value.count.return_value = count
        Fulfillment = Mock()
        item = SimpleNamespace(
            name="item",
            related_model=SimpleNamespace(
                _meta=SimpleNamespace(label_lower="core.orderitem"),
            ),
        )
        fields = [item, SimpleNamespace(name="status")]
        if include_kind:
            fields.append(SimpleNamespace(name="kind"))
        Fulfillment._meta.fields = fields
        queryset = Fulfillment.objects.filter.return_value
        queryset.count.return_value = grant_count
        queryset.values.return_value.distinct.return_value.count.return_value = unique_count
        return OrderItem, Fulfillment

    def run_recovery(self, **kwargs):
        orderitems, fulfillment = self.candidate(**kwargs)
        order = SimpleNamespace(pk=101)
        apps = Mock()
        apps.get_model.return_value = fulfillment
        with patch.dict(SCOPE, {"apps": apps, "OrderItem": orderitems}):
            result = SCOPE["_ready"](order)
        return result, fulfillment

    def test_completed_digital_grants_remain_recoverable(self):
        ready, model = self.run_recovery()
        self.assertTrue(ready)
        options = model.objects.filter.call_args.kwargs
        self.assertEqual(options["kind"], "digital")
        self.assertEqual(options["status__in"], ("ready", "complete"))
        self.assertEqual(options["item__order_id"], 101)

    def test_missing_or_duplicate_download_grant_is_never_all_ready(self):
        for grant_count, unique_count in ((1, 1), (2, 1), (3, 2)):
            with self.subTest(grants=grant_count, unique=unique_count):
                ready, _ = self.run_recovery(
                    grant_count=grant_count, unique_count=unique_count,
                )
                self.assertFalse(ready)

    def test_empty_order_does_not_have_any_downloadable_entitlement(self):
        result, fulfillment = self.run_recovery(count=0, grant_count=0, unique_count=0)
        self.assertFalse(result)
        fulfillment.objects.filter.assert_not_called()

    def test_missing_digital_kind_schema_fails_closed(self):
        result, fulfillment = self.run_recovery(include_kind=False)
        self.assertFalse(result)
        fulfillment.objects.filter.assert_not_called()


if __name__ == "__main__":
    unittest.main()
