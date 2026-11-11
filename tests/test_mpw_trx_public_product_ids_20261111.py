"""One public SKU allowlist policy across catalogue, guest GET and invoice POST.

Offline: no Django, payment, database, private files or network required.
"""
import importlib.util
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from types import ModuleType
import sys
from html import escape


SOURCE = Path(__file__).resolve().parents[1] / 'services/mpw_trx_commercial_context.py'
spec = importlib.util.spec_from_file_location('mpw_trx_public_ids_contract', SOURCE)
context = importlib.util.module_from_spec(spec)
spec.loader.exec_module(context)


class PublicProductIdsContract(unittest.TestCase):
    def test_missing_setting_is_empty_and_never_raises(self):
        self.assertEqual(context.public_product_ids(SimpleNamespace()), ())

    def test_three_explicit_ids_remain_available_for_eligible_products(self):
        settings = SimpleNamespace(MPW_TRX_PUBLIC_PRODUCT_IDS=(72, 225, 879))
        self.assertEqual(context.public_product_ids(settings), (72, 225, 879))

    def test_list_set_and_duplicates_have_stable_integer_result(self):
        for raw in ([879,72,72,225], {879,72,225}, frozenset((879,72,225))):
            with self.subTest(raw=raw):
                settings = SimpleNamespace(MPW_TRX_PUBLIC_PRODUCT_IDS=raw)
                self.assertEqual(context.public_product_ids(settings), (72,225,879))

    def test_bad_type_and_mixed_values_fail_closed(self):
        for raw in (None, 72, '72', {'72':True}, (72,'225'), (72,True), (72,0), (-1,72)):
            with self.subTest(raw=raw):
                settings = SimpleNamespace(MPW_TRX_PUBLIC_PRODUCT_IDS=raw)
                self.assertEqual(context.public_product_ids(settings), ())


class CatalogAllowlistContract(unittest.TestCase):
    def catalogue_ids(self, raw, *, include_product=False, hash_ok=True,
                      receiver_ready=True):
        modules = {}
        def put(name, **attrs):
            mod = ModuleType(name)
            mod.__dict__.update(attrs)
            modules[name] = mod
        settings = SimpleNamespace(MPW_TRX_PUBLIC_PRODUCT_IDS=raw)
        query = Mock()
        product = SimpleNamespace(pk=72, title='Chess', price='7.50')
        query.filter.return_value.order_by.return_value = [product] if include_product else []
        put('django')
        put('django.conf', settings=settings)
        put('django.db', connection=object())
        put('core')
        put('core.models', Product=SimpleNamespace(objects=query))
        put('mpw_commerce')
        put('mpw_commerce.buyer_orders', _eligible=lambda p: True)
        path = SimpleNamespace(is_symlink=lambda: False, is_file=lambda: True,
                               stat=lambda: SimpleNamespace(st_size=2048))
        put('mpw_commerce.downloads', _private_file=lambda item: path)
        put('services')
        put('services.mpw_walletless_commercial_intent',
            _commercial_db=lambda s, c: None)
        source = SOURCE.parent / 'mpw_trx_public_pages.py'
        tree = ast.parse(source.read_text('utf-8'))
        function = next(node for node in tree.body
                        if isinstance(node, ast.FunctionDef) and node.name == 'public_shop')
        function.decorator_list = []
        scope = {
            'Http404': RuntimeError,
            'PaymentHold': RuntimeError,
            'escape': escape,
            '_page': lambda title, content: (title, content),
            '_configured_receiver': (lambda: 'valid-recipient') if receiver_ready
                else (lambda: (_ for _ in ()).throw(RuntimeError('receiver missing'))),
            'public_product_ids': context.public_product_ids,
            'rights_cleared_for_sale': lambda p: True,
            'private_artifact_sha_matches_approved': lambda p, f: hash_ok,
        }
        with patch.dict(sys.modules, modules):
            exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), 'exec'),scope)
            request = SimpleNamespace(get_host=lambda: 'mojplaywin.com',
                                      is_secure=lambda: True)
            result = scope['public_shop'](request)
        return result, query.filter.call_args.kwargs.get('pk__in')

    def test_bad_configuration_returns_empty_catalogue_without_500(self):
        for raw in (None, '72', 72, {'72': True}, (72, '225')):
            with self.subTest(raw=raw):
                result, ids = self.catalogue_ids(raw)
                self.assertEqual(result[0], 'Buy digital products with TRX')
                self.assertEqual(ids, ())

    def test_three_valid_ids_reach_catalogue_query(self):
        result, ids = self.catalogue_ids((72,225,879))
        self.assertEqual(result[0], 'Buy digital products with TRX')
        self.assertEqual(ids, (72,225,879))

    def test_approved_stock_is_only_listed_if_real_file_digest_matches(self):
        approved, _ = self.catalogue_ids((72,225,879), include_product=True)
        changed, _ = self.catalogue_ids((72,225,879), include_product=True,
                                        hash_ok=False)
        self.assertIn('Chess', approved[1])
        self.assertNotIn('Chess', changed[1])

    def test_catalogue_refuses_to_advertise_unconfigured_receiver(self):
        with self.assertRaises(RuntimeError):
            self.catalogue_ids((72,225,879), include_product=True,
                               receiver_ready=False)


class AuthenticatedCheckoutStockContract(unittest.TestCase):
    def checkout(self, hash_ok):
        modules = {}
        def put(name, **attrs):
            mod = ModuleType(name)
            mod.__dict__.update(attrs)
            modules[name] = mod
        product = SimpleNamespace(pk=72, price=7.5)
        query = Mock()
        query.select_related.return_value.filter.return_value.first.return_value = product
        path = SimpleNamespace(is_symlink=lambda: False, is_file=lambda: True,
                               stat=lambda: SimpleNamespace(st_size=2048))
        render = Mock(return_value={'ok': True})
        put('django')
        put('django.conf', settings=SimpleNamespace(MPW_TRX_PUBLIC_PRODUCT_IDS=(72,)))
        put('django.shortcuts', render=render)
        put('core')
        put('core.models', Product=SimpleNamespace(objects=query))
        put('mpw_commerce')
        put('mpw_commerce.buyer_orders', _eligible=lambda p: True)
        put('mpw_commerce.downloads', _private_file=lambda item: path)
        source = SOURCE.parent / 'mpw_trx_public_pages.py'
        tree = ast.parse(source.read_text('utf-8'))
        function = next(node for node in tree.body
                        if isinstance(node, ast.FunctionDef) and node.name == 'product_checkout')
        function.decorator_list = []
        scope = {
            'Http404': RuntimeError,
            '_ensure_live': lambda r: None,
            '_nocache': lambda r: r,
            '_checkout_csrf_referrer': lambda r: r,
            'public_product_ids': context.public_product_ids,
            'rights_cleared_for_sale': lambda p: True,
            'private_artifact_sha_matches_approved': lambda p, path: hash_ok,
        }
        with patch.dict(sys.modules, modules):
            exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), 'exec'), scope)
            try:
                scope['product_checkout'](object(), 72)
                allowed = True
            except RuntimeError:
                allowed = False
        return allowed, render.call_count

    def test_approved_private_bytes_allow_checkout(self):
        self.assertEqual(self.checkout(True), (True, 1))

    def test_changed_private_bytes_do_not_render_checkout(self):
        self.assertEqual(self.checkout(False), (False, 0))


if __name__ == '__main__':
    unittest.main()
