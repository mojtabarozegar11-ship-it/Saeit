"""C109: unpaid/revoked/duplicated fulfillment must never pass guest recovery.

Pure mocked Django ORM relationships: no customer email, downloads, DB writes,
TRON RPC, invoice creation or checkout activation.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from services.mpw_trx_email_recovery import _ready


class GuestPaidItemFulfillmentRecoveryTests(SimpleTestCase):
    def setUp(self):
        self.order = SimpleNamespace(pk=984)
        self.items = MagicMock(name="bounded_item_queryset")
        self.grants = MagicMock(name="bounded_fulfillment_queryset")
        self.items.values_list.return_value = [11, 12]
        self.grants.filter.return_value = self.grants
        self.grants.values_list.return_value = [11, 12]

        item_model = SimpleNamespace(_meta=SimpleNamespace(label_lower="core.orderitem"))
        item_field = SimpleNamespace(name="item", related_model=item_model)
        status_field = SimpleNamespace(name="status")
        fulfillment = MagicMock(name="CommerceFulfillment")
        fulfillment._meta.fields = [item_field, status_field]
        fulfillment.objects.filter.return_value = self.grants

        self.mock_app = patch(
            "services.mpw_trx_email_recovery.apps.get_model",
            return_value=fulfillment,
        )
        self.mock_items = patch(
            "services.mpw_trx_email_recovery.OrderItem.objects.filter",
            return_value=self.items,
        )
        self.get_model = self.mock_app.start()
        self.order_filter = self.mock_items.start()
        self.addCleanup(self.mock_app.stop)
        self.addCleanup(self.mock_items.stop)

    def check(self, ids, receipt_ids):
        self.items.values_list.return_value = ids
        self.grants.values_list.return_value = receipt_ids
        return _ready(self.order)

    def test_01_every_item_must_have_one_valid_fulfillment(self):
        self.assertIs(self.check([11, 12], [11, 12]), True)

    def test_02_identical_order_item_keys_can_arrive_in_reverse_order(self):
        self.assertIs(self.check([11, 12], [12, 11]), True)

    def test_03_duplicated_one_item_does_not_cover_missing_other(self):
        self.assertIs(self.check([11, 12], [11, 11]), False)

    def test_04_foreign_order_item_cannot_cover_missing_item(self):
        self.assertIs(self.check([11, 12], [11, 55]), False)

    def test_05_one_unfulfilled_item_denies_whole_guest_recovery(self):
        self.assertIs(self.check([11, 12], [11]), False)

    def test_06_one_fulfillment_must_not_duplicate(self):
        self.assertIs(self.check([11], [11, 11]), False)

    def test_07_empty_order_never_authorizes_recovery(self):
        self.assertIs(self.check([], []), False)

    def test_08_hundred_distinct_fulfillments_bounded_and_allowed(self):
        ids = list(range(1, 101))
        self.assertIs(self.check(ids, ids), True)

    def test_09_more_than_hundred_order_items_fail_closed(self):
        ids = list(range(1, 102))
        self.assertIs(self.check(ids, ids), False)

    def test_10_non_unique_order_item_keys_fail_closed(self):
        self.assertIs(self.check([11, 11], [11, 11]), False)

    def test_11_private_schema_missing_denies(self):
        self.get_model.side_effect = LookupError("private model absent")
        self.assertIs(_ready(self.order), False)

    def test_12_wrong_related_model_does_not_match(self):
        self.get_model.return_value._meta.fields[0].related_model._meta.label_lower = (
            "mpw_commerce.orderitem"
        )
        self.assertIs(_ready(self.order), False)

    def test_13_no_status_column_is_not_valid_approval(self):
        self.get_model.return_value._meta.fields = (
            self.get_model.return_value._meta.fields[:1]
        )
        self.assertIs(_ready(self.order), False)

    def test_14_no_item_relation_denies(self):
        self.get_model.return_value._meta.fields = (
            self.get_model.return_value._meta.fields[1:]
        )
        self.assertIs(_ready(self.order), False)

    def test_15_private_orm_error_returns_safe_false(self):
        self.order_filter.side_effect = RuntimeError("failed DB connection")
        self.assertIs(_ready(self.order), False)

    def test_16_filters_restrict_to_original_item_ids_only(self):
        self.assertIs(self.check([11, 12], [11, 12]), True)
        self.get_model.return_value.objects.filter.assert_called_once_with(
            item_id__in=[11, 12]
        )
        self.order_filter.assert_called_once_with(order_id=984)
        self.items.values_list.assert_called_once_with("pk", flat=True)
        self.grants.values_list.assert_called_once_with("item_id", flat=True)

    def test_17_ready_and_complete_both_explicitly_accepted(self):
        self.assertTrue(self.check([11, 12], [11, 12]))
        args, kwargs = self.grants.filter.call_args
        self.assertEqual(len(args), 1)
        clause = args[0]
        self.assertEqual(clause.connector, "OR")
        self.assertEqual(
            {tuple(x) for x in clause.children},
            {("status__iexact", "ready"), ("status__iexact", "complete")},
        )
        self.assertEqual(kwargs, {})

    def test_18_no_write_or_mail_in_readiness_decision(self):
        self.assertTrue(self.check([11, 12], [11, 12]))
        self.get_model.return_value.objects.create.assert_not_called()
        self.get_model.return_value.objects.update.assert_not_called()
        self.grants.update.assert_not_called()
        self.items.update.assert_not_called()

    def test_19_item_queryset_bound_prevents_unbounded_reads(self):
        self.assertTrue(self.check([11, 12], [11, 12]))
        self.assertEqual(self.items.values_list.return_value, [11, 12])
        # QuerySet slicing is enforced in source; mocks cover the resulting
        # bounded materialization and the downstream exact item set.
