"""Integration checks: one AVA owner, brain, affect, goals and body gateway."""

import unittest

from ava_core import (
    AvaMemory, AvaRuntime, BodyCommand, ConsentError, GoalProposal,
    PersonalityTraits, SimulatedBody,
)


def internal_goal(goal_id="research"):
    return GoalProposal(
        goal_id=goal_id, description="Improve an internal research workflow",
        expected_value=5, feasibility=4, learning_value=5,
    )


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.model_calls = []

        def brain(messages):
            self.model_calls.append(messages)
            return "درود مجتبی جان"

        self.brain = brain
        self.runtime = AvaRuntime(
            owner_id="owner-1", brain=brain,
            propose_goals=lambda _: [internal_goal()],
            traits=PersonalityTraits(curiosity=2, humor=2),
        )

    def test_one_turn_passes_dynamic_affect_as_trusted_system_context(self):
        turn = self.runtime.converse("سلام آوا", affect_signal="new_idea")
        self.assertEqual(turn.reply.text, "درود مجتبی جان")
        self.assertEqual(turn.affect.curiosity, 3)
        self.assertEqual(turn.owner_id, "owner-1")
        messages = self.model_calls[-1]
        self.assertEqual(messages[-1], {"role": "user", "content": "سلام آوا"})
        self.assertTrue(any(m["role"] == "system" and "curiosity=3/5" in m["content"] for m in messages))

    def test_private_memory_flows_through_same_runtime_only_with_consent(self):
        with self.assertRaises(ConsentError):
            self.runtime.remember("private note")
        saved = self.runtime.remember("private note", consent=True)
        self.runtime.converse("سلام")
        self.assertNotIn("private note", str(self.model_calls[-1]))
        turn = self.runtime.converse("سلام", use_memories=True)
        self.assertEqual(turn.reply.memories_used, 1)
        self.assertIn("private note", str(self.model_calls[-1]))
        self.assertTrue(self.runtime.forget(saved.id))
        self.assertEqual(self.runtime.status().memory_items, 0)

    def test_goal_selection_and_evidence_share_lifecycle(self):
        decision = self.runtime.choose_goal()
        self.assertEqual(decision.selected.goal_id, "research")
        self.runtime.record_goal("research", completed=True, evidence="unit-test-evidence")
        self.assertEqual(self.runtime.status().goal_outcomes, 1)
        self.assertIsNone(self.runtime.choose_goal().selected)

    def test_simulation_denied_by_default_even_after_a_goal_was_chosen(self):
        self.runtime.choose_goal()
        command = BodyCommand(request_id="one", robot_id="ava-sim", kind="say", text="سلام")
        with self.assertRaises(PermissionError):
            self.runtime.simulate_body_command(command)

    def test_authorized_simulation_is_separate_from_goal_decision(self):
        body = SimulatedBody()
        runtime = AvaRuntime(
            owner_id="owner-1", brain=self.brain,
            propose_goals=lambda _: [internal_goal()], body=body,
            authorize_simulation=lambda owner, action: owner == "owner-1" and action.request_id == "s-1",
        )
        runtime.choose_goal()
        receipt = runtime.simulate_body_command(
            BodyCommand(request_id="s-1", robot_id="ava-sim", kind="say", text="سلام")
        )
        self.assertTrue(receipt.simulated)
        self.assertEqual(body.last_speech, "سلام")
        self.assertFalse(runtime.status().physical_actuation_enabled)

    def test_romantic_context_requires_independent_host_check(self):
        with self.assertRaises(PermissionError):
            self.runtime.set_romantic_mode(True)
        runtime = AvaRuntime(
            owner_id="owner-1", brain=self.brain,
            propose_goals=lambda _: (), authorize_romantic_session=lambda _: True,
        )
        runtime.set_romantic_mode(True)
        runtime.converse("درود")
        self.assertIn("non-explicit romantic warmth", str(self.model_calls[-1]))
        runtime.set_romantic_mode(False)
        runtime.converse("درود")
        self.assertIn("not enabled", str(self.model_calls[-1]))

    def test_owner_scoping_for_shared_opt_in_store(self):
        store = AvaMemory()
        other = AvaRuntime(owner_id="owner-2", brain=self.brain, propose_goals=lambda _: (), memory=store)
        first = AvaRuntime(owner_id="owner-1", brain=self.brain, propose_goals=lambda _: (), memory=store)
        item = first.remember("first owner's note", consent=True)
        self.assertEqual(other.status().memory_items, 0)
        self.assertFalse(other.forget(item.id))

    def test_status_does_not_exaggerate_model_or_physical_capability(self):
        state = self.runtime.status()
        self.assertFalse(state.brain_model_verified)
        self.assertFalse(state.physical_actuation_enabled)
        self.assertEqual(state.body.robot_id, "ava-sim")

    def test_no_implicit_effect_from_conversation(self):
        self.runtime.converse("لطفاً یک ربات بخر")
        self.assertEqual(self.runtime.status().goal_outcomes, 0)
        self.assertEqual(self.runtime.status().memory_items, 0)
        self.assertEqual(self.runtime.observe_body().robot_id, "ava-sim")

    def test_invalid_inputs_are_rejected_before_brain_call(self):
        with self.assertRaises(ValueError):
            self.runtime.converse("  ")
        with self.assertRaises(ValueError):
            self.runtime.converse("سلام", affect_signal="permission_granted")
        with self.assertRaises(ValueError):
            self.runtime.converse("سلام", affect_signal=[])
        self.assertEqual(len(self.model_calls), 0)

    def test_model_injection_is_mandatory_and_cannot_be_confused_with_a_real_model(self):
        with self.assertRaises(TypeError):
            AvaRuntime(owner_id="owner-1", brain=None, propose_goals=lambda _: ())
        with self.assertRaises(TypeError):
            AvaRuntime(owner_id="owner-1", brain=self.brain, propose_goals=None)


if __name__ == "__main__":
    unittest.main()
