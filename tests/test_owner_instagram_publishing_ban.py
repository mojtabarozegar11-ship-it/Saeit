"""Owner-specified permanent Instagram publishing exclusion — zero external calls."""
import unittest

from social_hub.adapters import Blocked, send
from social_hub.owner_policy import assert_destination_allowed, normalized_handle
from social_hub.service import run_one


def instagram(*, destination="17841401234567890",
              public_url="https://instagram.com/dr.mojtaba.rozegar/"):
    return {
        "brand": "mojplaywin", "platform": "instagram",
        "verified": True, "destination": destination, "public_url": public_url,
    }


class ForbiddenInstagramTests(unittest.TestCase):
    def test_explicit_profile_prohibited(self):
        with self.assertRaises(Blocked):
            assert_destination_allowed(instagram())

    def test_percent_encoded_profile_prohibited(self):
        with self.assertRaises(Blocked):
            assert_destination_allowed(instagram(public_url="https://www.instagram.com/dr%2Emojtaba%2Erozegar/"))

    def test_case_changes_prohibited(self):
        with self.assertRaises(Blocked):
            assert_destination_allowed(instagram(public_url="https://instagram.com/DR.Mojtaba.Rozegar/"))

    def test_punctuation_variants_prohibited(self):
        with self.assertRaises(Blocked):
            assert_destination_allowed(instagram(public_url="https://instagram.com/dr_mojtaba_rozegar/"))

    def test_destination_string_prohibited_even_if_url_elsewhere(self):
        with self.assertRaises(Blocked):
            assert_destination_allowed(instagram(destination="@Dr.Mojtaba.Rozegar",
                                                 public_url="https://instagram.com/other_account/"))

    def test_missing_profile_for_numeric_graph_id_prohibited(self):
        with self.assertRaises(Blocked):
            assert_destination_allowed(instagram(public_url=""))

    def test_unknown_profile_host_prohibited(self):
        with self.assertRaises(Blocked):
            assert_destination_allowed(instagram(public_url="https://not-instagram.example/dr.mojtaba.rozegar/"))

    def test_urls_with_query_are_prohibited(self):
        with self.assertRaises(Blocked):
            assert_destination_allowed(instagram(public_url="https://instagram.com/other_account/?id=1"))

    def test_mismatched_named_destination_prohibited(self):
        with self.assertRaises(Blocked):
            assert_destination_allowed(instagram(destination="@profile_one",
                                                 public_url="https://instagram.com/profile_two/"))

    def test_unrelated_instagram_profile_with_exact_identity_allowed_by_this_policy(self):
        assert_destination_allowed(instagram(destination="@allowed_company",
                                             public_url="https://instagram.com/allowed_company/"))

    def test_non_instagram_channels_not_blocked_by_instagram_rule(self):
        assert_destination_allowed({"platform": "telegram", "destination": "@allowed_company"})

    def test_send_rejects_before_transport(self):
        called = []
        with self.assertRaises(Blocked):
            send(instagram(), {"text": "Ordinary text", "image_url": "https://mojplaywin.com/x.webp"},
                 "never-use-token", lambda *args: called.append(args))
        self.assertEqual(called, [])

    def test_worker_rejects_before_credential_or_network(self):
        class FakeStore:
            def post(self, post_id):
                return {"id": post_id, "account_id": "123", "state": "approved",
                        "brand": "mojplaywin"}
            def account(self, account_id):
                return instagram()
        called = []
        with self.assertRaises(Blocked):
            run_one(FakeStore(), "post-1",
                    env={"MPW_SOCIAL_OUTBOUND_ENABLED": "1"},
                    execute=True,
                    transport=lambda *args: called.append(args))
        self.assertEqual(called, [])

    def test_normalization_exposes_encoded_alias(self):
        self.assertEqual(normalized_handle("DR%2EMOJTABA%2EROZEGAR"), "drmojtabarozegar")


if __name__ == "__main__":
    unittest.main()
