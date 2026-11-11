"""Deterministic checks for AVA's emerging self-directed goal selection."""

import unittest

from ava_core.goals import AutonomousGoalDirector, GoalProposal


def candidate(goal_id, value=3, feasibility=3, learning=3, **kwargs):
    return GoalProposal(
        goal_id=goal_id,
        description=f"Original proposed objective {goal_id}",
        expected_value=value,
        feasibility=feasibility,
        learning_value=learning,
        **kwargs,
    )


class GoalDirectorTests(unittest.TestCase):
    def test_selects_highest_scoring_internal_goal(self):
        goals = [candidate("low", 1), candidate("high", 5)]
        director = AutonomousGoalDirector(owner_id="person-1", proposer=lambda _: goals)
        decision = director.decide()
        self.assertEqual(decision.selected.goal_id, "high")
        self.assertEqual(len(decision.assessments), 2)

    def test_model_may_propose_novel_goals_without_human_task_list(self):
        seen = []

        def propose(history):
            seen.append(tuple(history))
            return [candidate("learn-pipeline" if not history else "improve-tests")]

        director = AutonomousGoalDirector(owner_id="person-1", proposer=propose)
        first = director.decide()
        director.record_outcome(first.selected.goal_id, completed=True, evidence="commit:abc")
        second = director.decide()
        self.assertEqual(second.selected.goal_id, "improve-tests")
        self.assertEqual(len(seen[1]), 1)

    def test_may_select_ambitious_goals_without_authorizing_actions(self):
        goals = [
            candidate("message", 5, external_effect=True),
            candidate("new-key", 5, requires_new_access=True),
            candidate("server", 5, estimated_spend_minor=1),
            candidate("offline-design", 1),
        ]
        director = AutonomousGoalDirector(owner_id="person-1", proposer=lambda _: goals)
        decision = director.decide()
        self.assertEqual(decision.selected.goal_id, "message")
        self.assertEqual(sum(a.eligible for a in decision.assessments), 4)
        self.assertIn("authorization required", decision.assessments[0].reason)
        self.assertIn("spending", decision.assessments[2].reason)

    def test_external_goal_remains_a_plan_not_an_executed_action(self):
        calls = []

        def proposal_provider(_):
            calls.append("proposed")
            return [candidate("purchase", external_effect=True)]

        director = AutonomousGoalDirector(owner_id="person-1", proposer=proposal_provider)
        self.assertEqual(director.decide().selected.goal_id, "purchase")
        self.assertEqual(calls, ["proposed"])
        self.assertEqual(director.history(), ())

    def test_goal_with_multiple_authorizations_still_selectable_for_planning(self):
        goal = candidate("expand-business", 5, external_effect=True,
                         requires_new_access=True, estimated_spend_minor=500)
        director = AutonomousGoalDirector(owner_id="person-1", proposer=lambda _: [goal])
        decision = director.decide()
        self.assertEqual(decision.selected, goal)
        for word in ("external action", "new access", "spending"):
            self.assertIn(word, decision.assessments[0].reason)

    def test_completed_goal_is_not_selected_again(self):
        director = AutonomousGoalDirector(owner_id="person-1", proposer=lambda _: [candidate("one")])
        director.decide()
        director.record_outcome("one", completed=True, evidence="passed tests")
        self.assertIsNone(director.decide().selected)

    def test_outcome_requires_evidence_and_current_selection(self):
        director = AutonomousGoalDirector(owner_id="person-1", proposer=lambda _: [candidate("one")])
        with self.assertRaises(ValueError):
            director.record_outcome("one", completed=True, evidence="x")
        director.decide()
        with self.assertRaises(ValueError):
            director.record_outcome("one", completed=True, evidence="   ")
        with self.assertRaises(ValueError):
            director.record_outcome("other", completed=True, evidence="x")
        self.assertEqual(director.record_outcome("one", completed=False, evidence="blocked").owner_id, "person-1")

    def test_rejects_bad_inputs_and_duplicate_ids(self):
        with self.assertRaises(ValueError):
            candidate("bad", value=6)
        with self.assertRaises(ValueError):
            candidate("bad", value=True)
        with self.assertRaises(ValueError):
            candidate("bad", estimated_spend_minor=-1)
        with self.assertRaises(ValueError):
            AutonomousGoalDirector(owner_id="", proposer=lambda _: ())
        director = AutonomousGoalDirector(owner_id="person-1", proposer=lambda _: [candidate("x"), candidate("x")])
        with self.assertRaises(ValueError):
            director.decide()

    def test_deterministic_tiebreak_and_owner_isolation(self):
        options = [candidate("z"), candidate("a")]
        first = AutonomousGoalDirector(owner_id="owner-a", proposer=lambda _: options)
        second = AutonomousGoalDirector(owner_id="owner-b", proposer=lambda _: options)
        self.assertEqual(first.decide().selected.goal_id, "a")
        first.record_outcome("a", completed=True, evidence="proof")
        self.assertEqual(len(second.history()), 0)
        self.assertEqual(second.decide().selected.goal_id, "a")


if __name__ == "__main__":
    unittest.main()
