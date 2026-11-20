"""Regression coverage for no replay after host runtime replacement."""
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
import unittest

from ava_core import MojtabaBot
from ava_core.capabilities import ActionRequest, AdapterResult, CapabilitySpec, OperationSpec


class SharedClaims:
    # Unit-test double, NOT evidence of persistence or production DB locking.
    def __init__(self):
        self.keys = set()
        self.lock = Lock()

    def reserve(self, request, operation):
        key = (request.owner_id, request.request_id)
        with self.lock:
            if key in self.keys:
                return False
            self.keys.add(key)
            return True


class ActionClaimsTests(unittest.TestCase):
    def setUp(self):
        self.store = SharedClaims()
        self.calls = []

    def bot(self, store=None, authorize=lambda *_: True, adapter=None):
        def record(request):
            self.calls.append(request.request_id)
            return AdapterResult(True, "local regression result")
        spec = CapabilitySpec("fixture", (OperationSpec("submit","write"), OperationSpec("inspect","read")))
        return MojtabaBot(owner_id="owner-1", brain=lambda _: "ok",
            propose_goals=lambda _: (), capabilities=((spec, adapter or record),),
            authorize_action=authorize, action_claim_store=store)

    def req(self, key="req-1", operation="submit"):
        return ActionRequest(key, "owner-1", "fixture", operation, {})

    def test_mutation_requires_store_even_when_authorized(self):
        with self.assertRaisesRegex(PermissionError, "Durable"):
            self.bot().execute_action(self.req())
        self.assertEqual(self.calls, [])

    def test_shared_store_rejects_replay_after_runtime_replacement(self):
        first = self.bot(self.store)
        self.assertTrue(first.status().durable_action_claim_store_configured)
        first.execute_action(self.req())
        with self.assertRaises(PermissionError):
            self.bot(self.store).execute_action(self.req())
        self.assertEqual(self.calls, ["req-1"])

    def test_failed_adapter_does_not_release_claim(self):
        def fail(_):
            raise RuntimeError("ambiguous outcome")
        with self.assertRaises(RuntimeError):
            self.bot(self.store, adapter=fail).execute_action(self.req())
        with self.assertRaises(PermissionError):
            self.bot(self.store).execute_action(self.req())
        self.assertEqual(self.calls, [])

    def test_denial_does_not_claim(self):
        with self.assertRaises(PermissionError):
            self.bot(self.store, authorize=lambda *_: False).execute_action(self.req())
        self.assertEqual(self.store.keys, set())

    def test_concurrent_duplicate_single_runtime(self):
        bot = self.bot(self.store)
        def execute(_):
            try:
                bot.execute_action(self.req())
                return True
            except PermissionError:
                return False
        with ThreadPoolExecutor(max_workers=4) as pool:
            self.assertEqual(sum(pool.map(execute, range(8))), 1)
        self.assertEqual(self.calls, ["req-1"])

    def test_read_compatibility_and_no_claim_attestation(self):
        bot = self.bot()
        self.assertFalse(bot.status().durable_action_claim_store_configured)
        self.assertFalse(bot.execute_action(self.req(operation="inspect")).independently_verified)
