"""Offline guest-email invoice source and dispatch safety contracts.

No Django import, runtime transaction, real payment, outbound email, or cPanel IO.
"""
import ast
import builtins
import importlib.util
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "scripts/mpw_guest_email_order_source_gate_20261114.py"
spec = importlib.util.spec_from_file_location("mpw_guest_email_gate", GATE)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

GUEST = '''
def _dispatch(request, view, args, kwargs, *, create=False):
    if create:
        from services.mpw_trx_email_recovery import bound_checkout
        return bound_checkout(request, view, _identity, _install_cookie, args, kwargs)
    return None

def _new_user(request):
    from services.mpw_trx_email_recovery import _posted_email
    submitted_email = _posted_email(request)
    user.email = submitted_email
    return user
'''
RECOVERY = '''
def _posted_email(request):
    return "safe@example.com"
def bound_checkout(request, view, identity, install_cookie, args, kwargs):
    return None
'''
MODELS = '''
class GuestOrderEmail: pass
class GuestRecoveryToken: pass
class GuestRecoveryRate: pass
'''
MIGRATION = '''
from django.db import migrations
class Migration:
    operations = [
        migrations.CreateModel(name="GuestOrderEmail"),
        migrations.CreateModel(name="GuestRecoveryToken"),
        migrations.CreateModel(name="GuestRecoveryRate"),
    ]
'''
REGISTRATION = '''
from .guest_recovery_models import GuestOrderEmail, GuestRecoveryToken, GuestRecoveryRate
'''


class SourceGateTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.sources = {
            "guest": GUEST, "recovery": RECOVERY, "models": MODELS,
            "migration": MIGRATION, "registration": REGISTRATION,
        }
        for name, rel in gate.RELATIVE.items():
            target = self.root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(self.sources[name], encoding="utf-8")

    def rewrite(self, name, text):
        (self.root / gate.RELATIVE[name]).write_text(text, encoding="utf-8")

    def test_full_synthetic_source_contract_still_never_approves_live_sale(self):
        result = gate.inspect(self.root)
        self.assertEqual(result["source_checks_passed"], 7)
        self.assertEqual(result["source_checks_total"], 7)
        self.assertTrue(result["source_candidate_complete"])
        self.assertFalse(result["production_release_permitted"])
        self.assertFalse(result["independent_trx_finality_verified"])
        self.assertFalse(result["paid_delivery_verified"])
        self.assertIsNone(result["commercial_revenue_verified"])

    def test_integrated_source_is_complete_but_still_never_authorizes_live_sale(self):
        result = gate.inspect(ROOT)
        self.assertEqual(result["source_checks_passed"], 7)
        self.assertEqual(result["source_checks_total"], 7)
        self.assertTrue(result["source_candidate_complete"])
        self.assertFalse(result["production_release_permitted"])
        self.assertFalse(result["migration_applied_verified"])
        self.assertFalse(result["passenger_runtime_verified"])
        self.assertIsNone(result["commercial_revenue_verified"])

    def test_missing_recovery_module_blocks_source_candidate(self):
        (self.root / gate.RELATIVE["recovery"]).unlink()
        result = gate.inspect(self.root)
        self.assertFalse(result["source_checks"]["email_binding_and_recovery_module"])
        self.assertFalse(result["source_candidate_complete"])

    def test_missing_email_write_blocks_source_candidate(self):
        self.rewrite("guest", GUEST.replace("user.email = submitted_email",
                                            "other = submitted_email"))
        self.assertFalse(gate.inspect(self.root)["source_checks"]
                         ["guest_principal_real_email_write"])

    def test_noncontactable_synthetic_guest_email_is_not_a_buyer_address(self):
        self.rewrite("guest", GUEST + '\nBAD="@guest.mojplaywin.invalid"\n')
        report = gate.inspect(self.root)
        self.assertFalse(report["source_checks"]["no_synthetic_guest_contact"])
        self.assertFalse(report["source_candidate_complete"])

    def test_dispatch_import_without_bound_return_does_not_pass(self):
        self.rewrite("guest", GUEST.replace(
            "return bound_checkout(request, view, _identity, _install_cookie, args, kwargs)",
            "return view(request, *args, **kwargs)"))
        self.assertFalse(gate.inspect(self.root)["source_checks"]
                         ["invoice_post_email_binding_guard"])

    def test_dispatch_guard_after_identity_call_does_not_pass(self):
        self.rewrite("guest", GUEST.replace(
            "    if create:", "    _identity(request, create=create)\n    if create:", 1))
        self.assertFalse(gate.inspect(self.root)["source_checks"]
                         ["invoice_post_email_binding_guard"])

    def test_missing_immutable_claim_model_blocks_candidate(self):
        self.rewrite("models", MODELS.replace("class GuestOrderEmail", "class Other"))
        self.assertFalse(gate.inspect(self.root)["source_checks"]
                         ["immutable_order_claim_models"])

    def test_missing_migration_create_model_blocks_candidate(self):
        self.rewrite("migration", MIGRATION.replace(
            'migrations.CreateModel(name="GuestOrderEmail"),', ""))
        self.assertFalse(gate.inspect(self.root)["source_checks"]
                         ["order_claim_migration_source"])

    def test_unregistered_claim_models_block_candidate(self):
        self.rewrite("registration", "from .guest_recovery_models import GuestRecoveryToken\n")
        self.assertFalse(gate.inspect(self.root)["source_checks"]
                         ["claim_model_registration"])

    def test_symlinked_recovery_source_cannot_qualify(self):
        link = self.root / gate.RELATIVE["recovery"]
        link.unlink()
        outside = self.root / "secrets"
        outside.write_text(RECOVERY, encoding="utf-8")
        link.symlink_to(outside)
        self.assertFalse(gate.inspect(self.root)["source_checks"]
                         ["email_binding_and_recovery_module"])

    def test_symlinked_parent_cannot_qualify(self):
        folder = self.root / "services"
        saved = self.root / "outside-services"
        folder.rename(saved)
        folder.symlink_to(saved, target_is_directory=True)
        result = gate.inspect(self.root)
        self.assertFalse(result["source_checks"]["invoice_post_email_binding_guard"])
        self.assertFalse(result["source_checks"]["email_binding_and_recovery_module"])

    def test_unparseable_or_oversized_recovery_fails_closed(self):
        for data in (b"def invalid(:\n", b"X" * (gate.LIMIT + 1), b"\xff\xfe"):
            with self.subTest(case=len(data)):
                (self.root / gate.RELATIVE["recovery"]).write_bytes(data)
                self.assertFalse(gate.inspect(self.root)["source_checks"]
                                 ["email_binding_and_recovery_module"])

    def test_source_gate_never_changes_or_exposes_source_text(self):
        all_files = [self.root / path for path in gate.RELATIVE.values()]
        before = {str(p): p.read_bytes() for p in all_files}
        result = gate.inspect(self.root)
        after = {str(p): p.read_bytes() for p in all_files}
        self.assertEqual(before, after)
        self.assertNotIn("safe@example.com", str(result))
        self.assertNotIn("guest_recovery_models.py", str(result))
        self.assertTrue(all(result[k] is False for k in (
            "customer_data_read", "database_accessed", "external_network_requests",
            "files_modified", "production_release_permitted",
        )))


class DispatchRuntimeTests(unittest.TestCase):
    def setUp(self):
        source = (ROOT / gate.RELATIVE["guest"]).read_text(encoding="utf-8")
        module = ast.parse(source)
        funcs = [n for n in module.body
                 if isinstance(n, ast.FunctionDef) and n.name == "_dispatch"]
        self.assertEqual(len(funcs), 1)
        self.user = object()
        self.token = "signed"
        self.identity = Mock(return_value=(self.user, self.token))
        self.cookie = Mock(side_effect=lambda response, token: response)
        self.view = Mock(return_value={"status_code": 200})
        class NotFound(Exception):
            pass
        self.Http404 = NotFound
        ns = {"_identity": self.identity, "_install_cookie": self.cookie,
              "Http404": NotFound}
        exec(compile(ast.Module(body=funcs, type_ignores=[]),
                     "<isolated_dispatch>", "exec"), ns)
        self.dispatch = ns["_dispatch"]
        self.original_import = builtins.__import__

    def _mock_import(self, bound=None, missing=False):
        def inner(name, *args, **kwargs):
            if name == "services.mpw_trx_email_recovery":
                if missing:
                    raise ImportError("no order-binding service installed")
                return types.SimpleNamespace(bound_checkout=bound)
            return self.original_import(name, *args, **kwargs)
        return patch("builtins.__import__", side_effect=inner)

    def test_guest_invoice_is_blocked_before_identity_or_invoice_if_no_binding(self):
        request = types.SimpleNamespace()
        with self._mock_import(missing=True):
            with self.assertRaisesRegex(self.Http404, "email order binding unavailable"):
                self.dispatch(request, self.view, (72,), {}, create=True)
        self.identity.assert_not_called()
        self.view.assert_not_called()
        self.cookie.assert_not_called()

    def test_noncallable_binding_cannot_issue_invoice(self):
        with self._mock_import(bound=None):
            with self.assertRaises(self.Http404):
                self.dispatch(object(), self.view, (), {}, create=True)
        self.identity.assert_not_called()
        self.view.assert_not_called()

    def test_installed_binding_receives_original_request_and_handler(self):
        response = {"redirect": "/commerce/trx-easy/invoice/123/"}
        bound = Mock(return_value=response)
        request = object()
        with self._mock_import(bound=bound):
            actual = self.dispatch(request, self.view, (72,), {"category": 5},
                                   create=True)
        self.assertIs(actual, response)
        bound.assert_called_once_with(
            request, self.view, self.identity, self.cookie,
            (72,), {"category": 5},
        )
        self.identity.assert_not_called()
        self.view.assert_not_called()

    def test_authenticated_checkout_keeps_existing_purchase_path_without_guest_recovery(self):
        request = types.SimpleNamespace(user=types.SimpleNamespace(
            is_authenticated=True))
        with self._mock_import(missing=True):
            response = self.dispatch(request, self.view, (72,), {}, create=True)
        self.assertEqual(response, {"status_code": 200})
        self.assertIs(request.user, self.user)
        self.identity.assert_called_once_with(request, create=False)
        self.view.assert_called_once_with(request, 72)
        self.cookie.assert_called_once_with(response, self.token)

    def test_noncreating_invoice_status_still_calls_legacy_owner_read(self):
        request = types.SimpleNamespace()
        response = self.dispatch(request, self.view, (17,), {}, create=False)
        self.assertEqual(response, {"status_code": 200})
        self.assertIs(request.user, self.user)
        self.identity.assert_called_once_with(request, create=False)
        self.view.assert_called_once_with(request, 17)
        self.cookie.assert_called_once_with(response, self.token)


if __name__ == "__main__":
    unittest.main()
