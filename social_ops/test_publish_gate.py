"""Publication gate regression tests: all unsafe cases fail closed."""
import unittest
from publish_gate import readiness

class PublicationGateTests(unittest.TestCase):
    def test_missing_connection_blocks_publication(self):
        draft = {"brand": "personal", "title": "Title", "text": "Body",
                 "status": "approved_for_publication",
                 "originality_checked": True, "rights_checked": True}
        result = readiness("personal", "instagram", draft, {})
        self.assertFalse(result["ready"])
        self.assertIn("account_not_verified", result["blockers"])

    def test_cross_brand_account_cannot_be_used(self):
        draft = {"brand": "company", "title": "Title", "text": "Body",
                 "status": "approved_for_publication",
                 "originality_checked": True, "rights_checked": True}
        account = {"personal": {"instagram": {"verified": True,
                   "authorized_to_publish": True, "integration_tested": True,
                   "account_id": "personal_account"}}}
        result = readiness("company", "instagram", draft, account)
        self.assertFalse(result["ready"])

    def test_fully_authorized_example(self):
        draft = {"brand": "mojplaywin", "title": "Title", "text": "Body",
                 "status": "approved_for_publication",
                 "originality_checked": True, "rights_checked": True}
        account = {"mojplaywin": {"youtube": {"verified": True,
                   "authorized_to_publish": True, "integration_tested": True,
                   "account_id": "example_only"}}}
        self.assertTrue(readiness("mojplaywin", "youtube", draft, account)["ready"])

if __name__ == "__main__":
    unittest.main()
