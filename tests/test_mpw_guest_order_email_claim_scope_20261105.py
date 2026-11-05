"""Offline behavior checks for guest checkout email claim isolation."""
from __future__ import annotations

import ast
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from contextvars import ContextVar
import hashlib
import hmac
from pathlib import Path
import re
import threading
from types import SimpleNamespace
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TestSourceContract(unittest.TestCase):
    def test_three_changed_modules_parse(self):
        for name in ("services/mpw_trx_email_recovery.py",
                     "services/mpw_trx_guest_commerce.py", "config/settings.py"):
            with self.subTest(name=name):
                ast.parse((ROOT / name).read_text("utf-8"))

    def test_capture_switch_independent_and_default_off(self):
        settings = (ROOT / "config/settings.py").read_text("utf-8")
        guest = (ROOT / "services/mpw_trx_guest_commerce.py").read_text("utf-8")
        self.assertIn('"MPW_GUEST_EMAIL_CLAIM_CAPTURE_ENABLED", default=False', settings)
        self.assertIn('getattr(settings, "MPW_GUEST_EMAIL_CLAIM_CAPTURE_ENABLED", False)', guest)
        self.assertIn('getattr(settings, "MPW_GUEST_RECOVERY_ENABLED", False)', guest)
        self.assertIn('getattr(settings, "MPW_GUEST_RECOVERY_EMAIL_APPROVED", False)', guest)

    def test_email_field_names_match_guest_account_and_immutable_claim(self):
        guest = (ROOT / "services/mpw_trx_guest_commerce.py").read_text("utf-8")
        recovery = (ROOT / "services/mpw_trx_email_recovery.py").read_text("utf-8")
        accepted = '("email", "buyer_email", "customer_email", "purchase_email", "purchaser_email")'
        self.assertEqual(guest.count(accepted), 2)
        self.assertEqual(recovery.count(accepted), 1)

    def test_public_routes_still_recovery_gated(self):
        tree = ast.parse((ROOT / "services/mpw_trx_guest_commerce.py").read_text("utf-8"))
        fn = next(x for x in tree.body if isinstance(x, ast.FunctionDef) and x.name == "patch_commercial")
        source = ast.get_source_segment((ROOT / "services/mpw_trx_guest_commerce.py").read_text("utf-8"), fn)
        self.assertIn('if getattr(settings, "MPW_GUEST_RECOVERY_ENABLED", False) is True:', source)
        self.assertIn('"commerce/trx-easy/recover/"', source)
        self.assertNotIn('MPW_GUEST_EMAIL_CLAIM_CAPTURE_ENABLED', source)

    def test_email_dispatch_remains_approval_gated(self):
        source = (ROOT / "services/mpw_trx_email_recovery.py").read_text("utf-8")
        self.assertIn('if getattr(settings, "MPW_GUEST_RECOVERY_EMAIL_APPROVED", False) is not True:', source)


class FakeSignal:
    def __init__(self):
        self.callbacks = {}
        self.lock = threading.RLock()

    def connect(self, fn, *, sender, weak, dispatch_uid):
        with self.lock:
            self.callbacks[dispatch_uid] = fn

    def disconnect(self, *, sender, dispatch_uid):
        with self.lock:
            self.callbacks.pop(dispatch_uid, None)

    def send_created(self, instance):
        with self.lock:
            callbacks = list(self.callbacks.values())
        for fn in callbacks:
            fn(sender=type(instance), instance=instance, created=True)


class FakeClaims:
    def __init__(self):
        self.rows = {}
        self.lock = threading.RLock()

    def create(self, *, order, email_address, email_digest):
        with self.lock:
            if order.pk in self.rows:
                raise RuntimeError("duplicate order email claim")
            self.rows[order.pk] = SimpleNamespace(
                order=order, email_address=email_address, email_digest=email_digest
            )

    def filter(self, *, order_id):
        row = self.rows.get(order_id)
        return SimpleNamespace(first=lambda: row)


class FakeIntents:
    def __init__(self):
        self.rows = {}

    def select_related(self, *_args):
        return self

    def filter(self, *, pk):
        return SimpleNamespace(first=lambda: self.rows.get(pk))


class TestCheckoutExecution(unittest.TestCase):
    def setUp(self):
        p = ROOT / "services/mpw_trx_email_recovery.py"
        source = p.read_text("utf-8")
        tree = ast.parse(source)
        fn = next(x for x in tree.body if isinstance(x, ast.FunctionDef) and x.name == "bound_checkout")
        self.signal = FakeSignal()
        self.claims = FakeClaims()
        self.intents = FakeIntents()
        self.scope = ContextVar("test_mpw_checkout_scope", default=None)
        class Http404(Exception):
            pass
        self.Http404 = Http404
        self.space = {
            "_host": lambda request: True,
            "_posted_email": lambda request: request.email,
            "_digest": lambda email: hashlib.sha256(email.encode()).hexdigest(),
            "_email": lambda email: email.strip().lower(),
            "_private": lambda response: response,
            "Http404": Http404,
            "HttpResponseBadRequest": lambda body: SimpleNamespace(status_code=400, body=body),
            "transaction": SimpleNamespace(atomic=lambda: nullcontext()),
            "_CHECKOUT_SIGNAL_SCOPE": self.scope,
            "post_save": self.signal,
            "Order": type("Order", (), {}),
            "GuestOrderEmail": SimpleNamespace(objects=self.claims),
            "PaymentIntent": SimpleNamespace(objects=self.intents),
            "INVOICE_RE": re.compile(r"\A/commerce/trx-easy/invoice/([1-9][0-9]*)/\Z"),
            "hmac": hmac,
        }
        exec(compile(ast.Module(body=[fn], type_ignores=[]), str(p), "exec"), self.space)
        self.checkout = self.space["bound_checkout"]

    def _request(self, pk, email):
        user = SimpleNamespace(pk=pk, has_usable_password=lambda: False)
        request = SimpleNamespace(email=email, user=user)
        return request, user

    def _run(self, pk, email, *, barrier=None, wrong_owner=False, emit=True):
        request, user = self._request(pk, email)
        def identity(req, *, create):
            return user, f"cookie-{pk}"
        def install_cookie(response, cookie):
            response.cookie = cookie
            return response
        def view(req):
            if barrier is not None:
                barrier.wait(timeout=5)
            order = SimpleNamespace(pk=pk * 100, customer_id=pk + int(wrong_owner))
            if emit:
                self.signal.send_created(order)
            intent = SimpleNamespace(order=order, order_id=order.pk)
            self.intents.rows[pk * 10] = intent
            return SimpleNamespace(status_code=302, get=lambda key, default=None: f"/commerce/trx-easy/invoice/{pk * 10}/")
        return self.checkout(request, view, identity, install_cookie, (), {})

    def test_two_concurrent_checkouts_do_not_cross_bind(self):
        barrier = threading.Barrier(2)
        with ThreadPoolExecutor(max_workers=2) as pool:
            a = pool.submit(self._run, 1, "first@example.org", barrier=barrier)
            b = pool.submit(self._run, 2, "second@example.org", barrier=barrier)
            self.assertEqual(a.result(timeout=8).cookie, "cookie-1")
            self.assertEqual(b.result(timeout=8).cookie, "cookie-2")
        self.assertEqual(set(self.claims.rows), {100, 200})
        self.assertEqual(self.claims.rows[100].email_address, "first@example.org")
        self.assertEqual(self.claims.rows[200].email_address, "second@example.org")
        self.assertEqual(len(self.signal.callbacks), 0)

    def test_wrong_owner_aborts(self):
        with self.assertRaisesRegex(ValueError, "guest owner"):
            self._run(3, "third@example.org", wrong_owner=True)
        self.assertIsNone(self.scope.get())
        self.assertFalse(self.signal.callbacks)

    def test_reused_legacy_order_without_immutable_claim_denied(self):
        with self.assertRaisesRegex(self.Http404, "ownership binding unavailable"):
            self._run(4, "legacy@example.org", emit=False)
        self.assertIsNone(self.scope.get())
        self.assertFalse(self.signal.callbacks)


if __name__ == "__main__":
    unittest.main()
