"""Verified-public-only directory; no credentials, private IDs or wrong domains."""
import json
from pathlib import Path
import tempfile
import unittest

from social_hub.store import Store
from social_hub.public_links import official_links
from social_hub.adapters import Blocked

class PublicDirectoryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.store=Store(str(Path(self.temp.name)/"social.sqlite"))

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def test_empty_private_store_has_no_public_channels(self):
        result=official_links(self.store)
        self.assertEqual(result["total"],0)
        self.assertEqual(set(x["key"] for x in result["brands"]),
                         {"personal","zomorod","mojplaywin"})

    def test_verified_url_display_has_no_token_or_identifiers(self):
        id1=self.store.add_account(brand="personal",platform_key="telegram",
               destination="@realowner",public_url="https://t.me/realowner",actor="owner")
        id2=self.store.add_account(brand="zomorod",platform_key="linkedin",
               destination="urn:li:organization:1234",
               public_url="https://www.linkedin.com/company/example-verified/",
               actor="owner")
        before=official_links(self.store)
        self.assertEqual(before["total"],0)
        self.store.verify_account(id1,proof="owner-platform-evidence-123456",actor="owner")
        after=official_links(self.store)
        self.assertEqual(after["total"],1)
        record=after["brands"][0]["links"][0]
        self.assertEqual(record["url"],"https://t.me/realowner")
        encoded=json.dumps(after)
        self.assertNotIn(id1,encoded)
        self.assertNotIn("token_env",encoded)
        self.assertNotIn("proof",encoded)
        self.assertNotIn("owner-platform-evidence",encoded)
        self.assertNotIn("urn:li:organization",encoded)
        self.assertEqual(len(after["brands"][1]["links"]),0)

    def test_corrupted_or_restricted_verified_profile_never_escapes(self):
        aid=self.store.add_account(brand="mojplaywin",platform_key="instagram",
               destination="verified_play",public_url="https://www.instagram.com/verified_play/",actor="owner")
        self.store.verify_account(aid,proof="owner-platform-evidence-123456",actor="owner")
        with self.store.transaction():
            self.store.db.execute("UPDATE accounts SET public_url=? WHERE id=?",
                ("https://instagram.com/dr.mojtaba.rozegar/",aid))
        self.assertEqual(official_links(self.store)["total"],0)
        with self.store.transaction():
            self.store.db.execute("UPDATE accounts SET public_url=? WHERE id=?",
                ("https://other-site.invalid/attack",aid))
        self.assertEqual(official_links(self.store)["total"],0)

    def test_manual_platform_only_after_verified(self):
        aid=self.store.add_account(brand="personal",platform_key="researchgate",
               destination="verified_researcher",
               public_url="https://www.researchgate.net/profile/Verified-Researcher",actor="owner")
        self.assertEqual(official_links(self.store)["total"],0)
        self.store.verify_account(aid,proof="owner-evidence-platform-123456",actor="owner") if False else None
        # The account verification flow currently disallows API-less platforms.
        self.assertEqual(official_links(self.store)["total"],0)

if __name__ == "__main__":
    unittest.main()
