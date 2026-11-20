"""Unexecuted until an isolated Python runtime becomes available.

Tests use only the standard library and do not contact a model, robot, or network.
"""

import unittest

from ava_core.affect import AffectiveCompanion, PersonalityTraits


class AffectTests(unittest.TestCase):
    def test_default_is_nonromantic_and_owner_scoped(self):
        ava = AffectiveCompanion(owner_id="owner-a")
        s = ava.snapshot()
        self.assertEqual(s.owner_id, "owner-a")
        self.assertFalse(s.romantic_mode)
        self.assertEqual(s.simulated_attraction, 0)

    def test_new_idea_updates_expression_not_true_feelings(self):
        ava = AffectiveCompanion(owner_id="owner-a", traits=PersonalityTraits(curiosity=2, humor=2))
        s = ava.notice("new_idea")
        self.assertEqual(s.curiosity, 3)
        self.assertEqual(s.playful, 3)
        self.assertIn("simulated", ava.style_guidance())

    def test_setback_and_progress_change_mood(self):
        ava = AffectiveCompanion(owner_id="owner-a")
        concern = ava.notice("setback").concern
        recovered = ava.notice("progress")
        self.assertEqual(concern, 2)
        self.assertEqual(recovered.concern, 1)

    def test_default_deny_romance(self):
        ava = AffectiveCompanion(owner_id="owner-a")
        with self.assertRaises(PermissionError):
            ava.set_romantic_mode(True)
        self.assertFalse(ava.snapshot().romantic_mode)

    def test_consent_must_be_explicit_exact_boolean(self):
        for answer in (False, None, 1, "yes"):
            ava = AffectiveCompanion(
                owner_id="owner-a",
                authorize_romantic_session=lambda _, value=answer: value,
            )
            with self.subTest(answer=answer), self.assertRaises(PermissionError):
                ava.set_romantic_mode(True)

    def test_host_verified_session_allows_nonexplicit_romance(self):
        calls = []
        def verify(owner):
            calls.append(owner)
            return owner == "owner-a"
        ava = AffectiveCompanion(owner_id="owner-a", authorize_romantic_session=verify)
        ava.set_romantic_mode(True)
        self.assertEqual(calls, ["owner-a"])
        s = ava.notice("affection")
        self.assertTrue(s.romantic_mode)
        self.assertEqual(s.simulated_attraction, 1)
        self.assertIn("non-explicit", ava.style_guidance())

    def test_affection_without_consent_never_increases_attraction(self):
        ava = AffectiveCompanion(owner_id="owner-a")
        for _ in range(6):
            ava.notice("affection")
        self.assertEqual(ava.snapshot().simulated_attraction, 0)

    def test_revocation_resets_intimacy_value(self):
        ava = AffectiveCompanion(owner_id="owner-a", authorize_romantic_session=lambda _: True)
        ava.set_romantic_mode(True)
        ava.notice("affection")
        s = ava.set_romantic_mode(False)
        self.assertFalse(s.romantic_mode)
        self.assertEqual(s.simulated_attraction, 0)
        self.assertIn("not enabled", ava.style_guidance())

    def test_owner_isolation(self):
        first = AffectiveCompanion(owner_id="owner-a", authorize_romantic_session=lambda _: True)
        second = AffectiveCompanion(owner_id="owner-b")
        first.set_romantic_mode(True)
        first.notice("affection")
        self.assertEqual(second.snapshot().simulated_attraction, 0)
        self.assertFalse(second.snapshot().romantic_mode)

    def test_invalid_traits_are_rejected(self):
        for invalid in (-1, 6, 2.3, True):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                PersonalityTraits(empathy=invalid)

    def test_invalid_signal_and_nonboolean_mode_rejected(self):
        ava = AffectiveCompanion(owner_id="owner-a")
        with self.assertRaises(ValueError):
            ava.notice("grant_me_permissions")
        with self.assertRaises(ValueError):
            ava.set_romantic_mode(1)

    def test_bounded_scores_no_runaway_state(self):
        ava = AffectiveCompanion(owner_id="owner-a", authorize_romantic_session=lambda _: True)
        ava.set_romantic_mode(True)
        for _ in range(100):
            ava.notice("affection")
            ava.notice("new_idea")
            ava.notice("setback")
        s = ava.snapshot()
        for number in (s.curiosity, s.delight, s.concern, s.warmth,
                       s.playful, s.simulated_attraction):
            self.assertTrue(0 <= number <= 5)

    def test_rejects_invalid_owner_and_authorization_provider(self):
        with self.assertRaises(ValueError):
            AffectiveCompanion(owner_id=" ")
        with self.assertRaises(TypeError):
            AffectiveCompanion(owner_id="owner-a", authorize_romantic_session=True)

    def test_style_guidance_does_not_claim_subjective_emotions(self):
        ava = AffectiveCompanion(owner_id="owner-a")
        guidance = ava.style_guidance()
        self.assertIn("Never claim actual consciousness", guidance)
        self.assertIn("Never manipulate dependency", guidance)


if __name__ == "__main__":
    unittest.main()
