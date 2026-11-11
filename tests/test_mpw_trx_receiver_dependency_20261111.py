"""Run the actual native TRON address contract without payments or network.

The guest invoice adapter must not import the absent historical
scripts.mojplaywin_native_chain_verify module.  The existing local F41
Base58Check validator is sufficient for address syntax, not ownership proof.
"""
import ast
from pathlib import Path
import secrets
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
RECEIVER = 'THFNU1iEXHd71WjEgjqUksd2UnMg2pUi73'


class PaymentHold(Exception):
    pass


class ReachedDatabaseAllocation(Exception):
    pass


def isolate(relative, function, scope):
    file = ROOT / relative
    tree = ast.parse(file.read_text('utf-8'))
    matches = [node for node in tree.body
               if isinstance(node, ast.FunctionDef) and node.name == function]
    assert len(matches) == 1
    exec(compile(ast.Module(body=matches, type_ignores=[]), str(file), 'exec'), scope)
    return scope[function]


def module(name, **fields):
    obj = ModuleType(name)
    obj.__dict__.update(fields)
    return obj


class NativeTRXReceiverContract(unittest.TestCase):
    def configured(self, receivers):
        imports = {
            'mpw_commerce': module('mpw_commerce'),
            'mpw_commerce.invoicing': module('mpw_commerce.invoicing', RECEIVERS=receivers),
        }
        scope = {'PaymentHold': PaymentHold}
        with patch.dict(sys.modules, imports):
            view = isolate('services/mpw_trx_commercial_web.py',
                           '_configured_receiver', scope)
            return view()

    def test_real_mainnet_base58check_receiver_is_accepted(self):
        self.assertEqual(self.configured({'TRX': ('tron-mainnet', RECEIVER, 6)}), RECEIVER)

    def test_bad_checksum_receiver_is_rejected(self):
        invalid = RECEIVER[:-1] + ('4' if RECEIVER[-1] != '4' else '5')
        with self.assertRaisesRegex(PaymentHold, 'invalid'):
            self.configured({'TRX': ('tron-mainnet', invalid, 6)})

    def test_missing_and_wrong_chain_receivers_are_rejected(self):
        for recipients in ({}, {'TRX': ('shasta', RECEIVER, 6)},
                           {'TRX': ('tron-mainnet', RECEIVER, 18)},
                           {'TRX': ('tron-mainnet', None, 6)}):
            with self.subTest(recipients=recipients):
                with self.assertRaises(PaymentHold):
                    self.configured(recipients)

    def reserve(self, address):
        imports = {
            'django': module('django'),
            'django.conf': module('django.conf', settings=object()),
            'django.db': module('django.db', connection=object(), transaction=object()),
            'django.utils': module('django.utils'),
            'django.utils.timezone': module('django.utils.timezone', now=lambda: None),
            'core': module('core'),
            'core.models': module('core.models', Order=object(), PaymentIntent=object()),
            'mpw_commerce': module('mpw_commerce'),
            'mpw_commerce.models': module('mpw_commerce.models', CommerceInvoice=object()),
        }
        def stop_at_database(db):
            raise ReachedDatabaseAllocation()
        scope = {'PaymentHold': PaymentHold, 'secrets': secrets,
                 '_commercial_db': lambda settings, db: None,
                 '_allocation_lock': stop_at_database}
        with patch.dict(sys.modules, imports):
            issue = isolate('services/mpw_walletless_commercial_intent.py',
                            'reserve_commercial_intent', scope)
            return issue(77, 8, rate_provider=lambda: None,
                         configured_receiver=lambda: address)

    def test_invoice_rejects_invalid_address_before_database_lock(self):
        with self.assertRaisesRegex(PaymentHold, 'Invalid merchant-owned'):
            self.reserve(RECEIVER[:-1] + '4')

    def test_valid_address_passes_exact_validation_into_reservation(self):
        with self.assertRaises(ReachedDatabaseAllocation):
            self.reserve(RECEIVER)


if __name__ == '__main__':
    unittest.main()
