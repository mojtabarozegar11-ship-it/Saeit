"""Security regression tests for the unified assistant's action gate."""
import unittest

from ava_core.action_policy import Action, ActionRequest, Decision, authorize


class ActionPolicyTests(unittest.TestCase):
    def request(self, action, **overrides):
        data = dict(owner_id="owner", action=action, resource_id="item-1",
                    authenticated=True)
        data.update(overrides)
        return ActionRequest(**data)

    def test_unauthenticated_denied_even_for_read(self):
        self.assertEqual(authorize(self.request(Action.READ_OWN_DATA,
                                                authenticated=False)), Decision.DENY)

    def test_local_draft_allowed_only_after_authentication(self):
        self.assertEqual(authorize(self.request(Action.LOCAL_DRAFT)), Decision.ALLOW)

    def test_every_sensitive_action_requires_specific_approval(self):
        for action in (Action.SEND_MESSAGE, Action.PUBLISH, Action.LIVE_TRADE,
                       Action.TRANSFER_FUNDS, Action.CHANGE_ACCESS,
                       Action.DELETE_DATA, Action.DEPLOY):
            with self.subTest(action=action):
                self.assertEqual(authorize(self.request(action)), Decision.REQUIRE_APPROVAL)

    def test_exact_verified_approval_allows_only_matching_action_and_resource(self):
        approved = self.request(Action.LIVE_TRADE, approval_verified=True,
                                approved_action=Action.LIVE_TRADE,
                                approved_resource_id="item-1")
        self.assertEqual(authorize(approved), Decision.ALLOW)
        self.assertEqual(authorize(self.request(Action.TRANSFER_FUNDS,
                                                approval_verified=True,
                                                approved_action=Action.LIVE_TRADE,
                                                approved_resource_id="item-1")),
                         Decision.REQUIRE_APPROVAL)
        self.assertEqual(authorize(self.request(Action.LIVE_TRADE,
                                                approval_verified=True,
                                                approved_action=Action.LIVE_TRADE,
                                                approved_resource_id="item-2")),
                         Decision.REQUIRE_APPROVAL)

    def test_unverified_approval_cannot_authorize(self):
        self.assertEqual(authorize(self.request(Action.DEPLOY,
                                                approved_action=Action.DEPLOY,
                                                approved_resource_id="item-1")),
                         Decision.REQUIRE_APPROVAL)

    def test_invalid_identity_or_action_denied(self):
        self.assertEqual(authorize(self.request(Action.LOCAL_DRAFT,
                                                owner_id=" ")), Decision.DENY)
        self.assertEqual(authorize(self.request("unknown")), Decision.DENY)


if __name__ == "__main__":
    unittest.main()
