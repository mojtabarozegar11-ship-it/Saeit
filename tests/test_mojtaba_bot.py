"""The single canonical bot, its capability bus and authority boundaries."""

import unittest

from ava_core import (
    ActionRequest, AdapterResult, AvaRuntime, CapabilityHub, CapabilitySpec,
    ConversationEngine, MojtabaBot, OperationSpec,
)


def spec(name="management", effect="local"):
    return CapabilitySpec(name, (OperationSpec("run", effect),))


def action(request_id="action-1", owner="owner", capability="management"):
    return ActionRequest(request_id, owner, capability, "run", {"project": "Mojtaba.bot.ai"})


class UnifiedBotTests(unittest.TestCase):
    def test_mojtaba_bot_is_the_one_runtime_class(self):
        self.assertIs(AvaRuntime, MojtabaBot)
        self.assertEqual(MojtabaBot(owner_id="owner", brain=lambda _: "ok",
                                    propose_goals=lambda _: ()).bot_name, "Mojtaba.bot.ai")

    def test_ava_is_not_a_second_conversational_class(self):
        from ava_core import Ava
        self.assertIs(Ava, ConversationEngine)
        self.assertIn("Mojtaba.bot.ai", Ava.SYSTEM_GUIDANCE)
        self.assertIn("not a separate bot", Ava.SYSTEM_GUIDANCE)

    def test_single_bot_hosts_multiple_domains(self):
        called = []
        def adapter(request):
            called.append((request.capability, request.operation))
            return AdapterResult(True, "Completed internal calculation")
        bot = MojtabaBot(owner_id="owner", brain=lambda _: "hello",
                         propose_goals=lambda _: (), capabilities=(
                             (spec("research"), adapter),
                             (spec("games"), adapter),
                             (spec("products"), adapter),
                         ))
        for name in ("research", "games", "products"):
            receipt = bot.execute_action(action(name, capability=name))
            self.assertEqual(receipt.owner_id, "owner")
        self.assertEqual(len(bot.connected_capabilities()), 3)
        self.assertEqual(called, [(name, "run") for name in ("research", "games", "products")])
        self.assertFalse(bot.execute_action.__self__.capabilities.receipt("research").independently_verified)

    def test_unconnected_domains_are_not_falsely_reported(self):
        bot = MojtabaBot(owner_id="owner", brain=lambda _: "ok", propose_goals=lambda _: ())
        self.assertEqual(bot.connected_capabilities(), ())
        with self.assertRaises(LookupError):
            bot.execute_action(action())

    def test_local_operation_does_not_need_external_authorization(self):
        calls = []
        hub = CapabilityHub(owner_id="owner")
        hub.register(spec(), lambda request: (calls.append(request.request_id), AdapterResult(True, "done"))[1])
        receipt = hub.execute(action())
        self.assertTrue(receipt.result.success)
        self.assertEqual(calls, ["action-1"])

    def test_external_effects_default_to_no_authority(self):
        for effect in ("read", "write", "financial", "destructive", "physical"):
            with self.subTest(effect=effect):
                calls = []
                hub = CapabilityHub(owner_id="owner")
                hub.register(spec(effect=effect), lambda _: calls.append("executed"))
                with self.assertRaises(PermissionError):
                    hub.execute(action())
                self.assertEqual(calls, [])

    def test_host_authorization_is_bound_to_exact_action(self):
        audited = []
        hub = CapabilityHub(
            owner_id="owner",
            authorize=lambda owner, request, operation: (
                audited.append((owner, request.request_id, operation.effect))
                or request.request_id == "approved-42"
            ),
        )
        hub.register(spec(effect="write"), lambda _: AdapterResult(True, "updated", "record-42"))
        with self.assertRaises(PermissionError):
            hub.execute(action("not-approved"))
        receipt = hub.execute(action("approved-42"))
        self.assertEqual(receipt.result.evidence_reference, "record-42")
        self.assertFalse(receipt.independently_verified)
        self.assertEqual(audited, [("owner", "not-approved", "write"),
                                   ("owner", "approved-42", "write")])

    def test_authorizer_must_return_boolean_true(self):
        hub = CapabilityHub(owner_id="owner", authorize=lambda *_: 1)
        hub.register(spec(effect="financial"), lambda _: AdapterResult(True, "paid"))
        with self.assertRaises(PermissionError):
            hub.execute(action())

    def test_replay_is_refused_even_after_success(self):
        count = []
        hub = CapabilityHub(owner_id="owner")
        hub.register(spec(), lambda _: (count.append(1), AdapterResult(True, "done"))[1])
        first = hub.execute(action())
        with self.assertRaises(PermissionError):
            hub.execute(action())
        self.assertEqual(hub.receipt("action-1"), first)
        self.assertEqual(count, [1])

    def test_replay_is_refused_after_ambiguous_adapter_failure(self):
        count = []
        def failed_adapter(_):
            count.append(1)
            raise RuntimeError("connection dropped after side effect")
        hub = CapabilityHub(owner_id="owner")
        hub.register(spec(), failed_adapter)
        with self.assertRaises(RuntimeError):
            hub.execute(action())
        with self.assertRaises(PermissionError):
            hub.execute(action())
        self.assertEqual(count, [1])

    def test_owner_mismatch_never_calls_adapter(self):
        count = []
        hub = CapabilityHub(owner_id="owner")
        hub.register(spec(), lambda _: count.append(1))
        with self.assertRaises(PermissionError):
            hub.execute(action(owner="attacker"))
        self.assertEqual(count, [])

    def test_duplicate_module_and_undeclared_operation_rejected(self):
        hub = CapabilityHub(owner_id="owner")
        hub.register(spec(), lambda _: AdapterResult(True, "ok"))
        with self.assertRaises(ValueError):
            hub.register(spec(), lambda _: AdapterResult(True, "ok"))
        with self.assertRaises(ValueError):
            hub.execute(ActionRequest("req2", "owner", "management", "undeclared", {}))

    def test_bad_metadata_and_results_are_rejected(self):
        with self.assertRaises(ValueError):
            OperationSpec("run", "unspecified")
        with self.assertRaises(ValueError):
            CapabilitySpec("dup", (OperationSpec("run", "local"), OperationSpec("run", "write")))
        with self.assertRaises(TypeError):
            ActionRequest("a", "owner", "management", "run", [])
        with self.assertRaises(ValueError):
            AdapterResult(True, "")
        hub = CapabilityHub(owner_id="owner")
        hub.register(spec(), lambda _: "unverified success")
        with self.assertRaises(TypeError):
            hub.execute(action())
        with self.assertRaises(PermissionError):
            hub.execute(action())

    def test_host_authorizes_immutable_exact_request_data(self):
        arguments = {"values": [1, {"amount": 3}], "project": "trading"}
        request = ActionRequest("safe-id", "owner", "management", "run", arguments)
        arguments["values"][1]["amount"] = 9000
        self.assertEqual(request.arguments["values"][1]["amount"], 3)
        with self.assertRaises(TypeError):
            request.arguments["project"] = "mutated"
        with self.assertRaises(TypeError):
            request.arguments["values"][1]["amount"] = 100
        with self.assertRaises(TypeError):
            ActionRequest("bad", "owner", "management", "run", {"callback": lambda: None})

    def test_one_bot_owns_conversation_goals_code_and_modules(self):
        bot = MojtabaBot(owner_id="owner", brain=lambda _: "hello",
                         propose_goals=lambda _: (), capabilities=((
                             spec("tools"), lambda _: AdapterResult(True, "available")
                         ),))
        self.assertEqual(bot.converse("سلام").reply.text, "hello")
        self.assertEqual(bot.choose_goal().owner_id, "owner")
        self.assertEqual(bot.evolution.owner_id, "owner")
        self.assertEqual(bot.capabilities.owner_id, "owner")
        self.assertEqual(bot.execute_action(action("tools-1", capability="tools")).result.detail,
                         "available")


if __name__ == "__main__":
    unittest.main()
