"""Offline behavior tests for the three-SKU private-stock sales guard.

No Django installation, network, database, or payable order is required.
"""
import ast
import contextlib
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest import TestCase, main
from unittest.mock import Mock, patch
import sys


ROOT = Path(__file__).resolve().parents[1]


class NotFound(Exception):
    pass


class PaymentHold(Exception):
    pass


def isolate_function(relative_path, name, scope):
    source = ROOT / relative_path
    tree = ast.parse(source.read_text('utf-8'))
    functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name]
    assert len(functions) == 1
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(source), 'exec'), scope)
    return scope[name]


def put(modules, name, **attrs):
    module = ModuleType(name)
    module.__dict__.update(attrs)
    modules[name] = module
    return module


def private_asset(*, present=True, size=1024, symlink=False):
    return SimpleNamespace(is_symlink=lambda: symlink,
                           is_file=lambda: present,
                           stat=lambda: SimpleNamespace(st_size=size))


class GuestCheckoutPrivateStockTests(TestCase):
    def checkout(self, asset):
        modules = {}
        render = Mock(return_value={})
        query = Mock()
        query.select_related.return_value.filter.return_value.first.return_value = SimpleNamespace(
            pk=72, title='Chess', price=Decimal('7.50'))
        private = Mock(side_effect=asset if isinstance(asset, Exception) else None)
        if not isinstance(asset, Exception):
            private.return_value = asset
        put(modules, 'django')
        put(modules, 'django.conf', settings=SimpleNamespace(MPW_TRX_PUBLIC_PRODUCT_IDS=(72,225,879)))
        put(modules, 'django.db', connection=object())
        put(modules, 'django.shortcuts', render=render)
        put(modules, 'core')
        put(modules, 'core.models', Product=SimpleNamespace(objects=query))
        put(modules, 'mpw_commerce')
        put(modules, 'mpw_commerce.buyer_orders', _eligible=lambda p: True)
        put(modules, 'mpw_commerce.downloads', _private_file=private)
        put(modules, 'services')
        put(modules, 'services.mpw_trx_commercial_context', rights_cleared_for_sale=lambda p: True)
        put(modules, 'services.mpw_trx_commercial_web',
            _configured_receiver=lambda: True, _nocache=lambda response: response)
        put(modules, 'services.mpw_walletless_commercial_intent', _commercial_db=lambda s,c: True)
        request = object()
        with patch.dict(sys.modules, modules):
            view = isolate_function('services/mpw_trx_guest_commerce.py', '_checkout_page', {
                'Http404': NotFound,
                '_host_ok': lambda r: True,
                '_record_funnel_event_best_effort': Mock(),
            })
            namespace = {'_checkout_csrf_referrer': lambda response: response}
            try:
                response = view(request, 72, namespace)
            except NotFound:
                response = None
        return response, render.call_count, private.call_count

    def test_existing_positive_size_asset_renders_checkout(self):
        response, rendered, looked_up = self.checkout(private_asset())
        self.assertIsNotNone(response)
        self.assertEqual(rendered, 1)
        self.assertEqual(looked_up, 1)

    def test_missing_private_file_never_renders_checkout(self):
        response, rendered, looked_up = self.checkout(FileNotFoundError('unavailable'))
        self.assertIsNone(response)
        self.assertEqual(rendered, 0)
        self.assertEqual(looked_up, 1)

    def test_zero_byte_asset_never_renders_checkout(self):
        self.assertEqual(self.checkout(private_asset(size=0))[1], 0)

    def test_symlink_asset_never_renders_checkout(self):
        self.assertEqual(self.checkout(private_asset(symlink=True))[1], 0)

    def test_non_file_asset_never_renders_checkout(self):
        self.assertEqual(self.checkout(private_asset(present=False))[1], 0)


class ExistingInvoicePrivateStockTests(TestCase):
    def existing_invoice(self, asset):
        now = datetime(2026, 11, 11, tzinfo=timezone.utc)
        modules = {}
        product = SimpleNamespace(pk=72, price=Decimal('7.50'))
        product_model = SimpleNamespace(objects=Mock())
        product_model.objects.select_for_update.return_value.get.return_value = product
        old_order = SimpleNamespace(pk=20)
        order_model = SimpleNamespace(objects=Mock())
        order_model.objects.select_for_update.return_value.filter.return_value.order_by.return_value.__getitem__ = Mock(return_value=[old_order])
        order_item_model = SimpleNamespace(objects=Mock())
        order_item_model.objects.filter.return_value = [SimpleNamespace(product_id=72)]
        invoice_model = SimpleNamespace(objects=Mock())
        invoice_model.objects.filter.return_value.first.return_value = SimpleNamespace(pk=59)
        private = Mock(side_effect=asset if isinstance(asset, Exception) else None)
        if not isinstance(asset, Exception):
            private.return_value = asset
        put(modules, 'django')
        put(modules, 'django.contrib')
        put(modules, 'django.contrib.auth', get_user_model=lambda: SimpleNamespace(objects=Mock()))
        put(modules, 'django.db', transaction=SimpleNamespace(atomic=lambda **kw: contextlib.nullcontext()))
        put(modules, 'django.utils')
        put(modules, 'django.utils.timezone', now=lambda: now)
        put(modules, 'django.http', Http404=NotFound)
        put(modules, 'core')
        put(modules, 'core.models', Product=product_model, Order=order_model,
            OrderItem=order_item_model, PaymentIntent=invoice_model)
        put(modules, 'mpw_commerce')
        put(modules, 'mpw_commerce.buyer_orders', _eligible=lambda p: True)
        put(modules, 'mpw_commerce.downloads', _private_file=private)
        with patch.dict(sys.modules, modules):
            view = isolate_function('services/mpw_trx_commercial_web.py', '_select_order', {
                'PaymentHold': PaymentHold,
                'Decimal': Decimal,
                'timedelta': timedelta,
                'PROVIDER': 'tron',
                'WAITING': 'awaiting_chain',
                '_decode': lambda invoice: SimpleNamespace(expires_at=now+timedelta(minutes=4)),
                'rights_cleared_for_sale': lambda p: True,
                'reserve_commercial_intent': Mock(),
            })
            try:
                result = view(72, 7, SimpleNamespace(alias='default'))
            except PaymentHold:
                result = None
        return result, private.call_count, invoice_model.objects.filter.call_count

    def test_reuses_existing_invoice_only_when_stock_still_exists(self):
        result, private_calls, invoice_queries = self.existing_invoice(private_asset())
        self.assertEqual(result, 59)
        self.assertEqual(private_calls, 1)
        self.assertEqual(invoice_queries, 1)

    def test_does_not_reuse_invoice_when_asset_went_missing(self):
        result, private_calls, invoice_queries = self.existing_invoice(FileNotFoundError('gone'))
        self.assertIsNone(result)
        self.assertEqual(private_calls, 1)
        self.assertEqual(invoice_queries, 0)

    def test_does_not_reuse_invoice_for_empty_stock(self):
        self.assertIsNone(self.existing_invoice(private_asset(size=0))[0])

    def test_does_not_reuse_invoice_for_symlink_stock(self):
        self.assertIsNone(self.existing_invoice(private_asset(symlink=True))[0])


if __name__ == '__main__':
    main()
