import unittest
from scripts.mojprop_migration_quota_readonly_20261119 import history, quota_summary, EXPECTED

class FocusedAuditTests(unittest.TestCase):
    def test_known_prefix(self):
        out=history(EXPECTED[:11])
        self.assertTrue(out["contiguous_known_prefix"])
        self.assertEqual(len(out["known_unrecorded_migrations"]),6)
    def test_gap(self):
        self.assertFalse(history([EXPECTED[0],EXPECTED[2]])["contiguous_known_prefix"])
    def test_unknown_migration_is_not_disclosed(self):
        out=history(["unexpected-sensitive-name"])
        self.assertEqual(out["unknown_record_count"],1)
        self.assertNotIn("unexpected-sensitive-name",str(out))
    def test_reported_quota_only(self):
        out=quota_summary({"result":{"status":1,"data":[{"id":"diskusage","units":"MB","count":"100.5","max":"200"}]}})
        self.assertTrue(out["recognized"])
        self.assertEqual(out["reported_remaining"],"99.5")
        self.assertFalse(out["account_headroom_verified"])
    def test_unlimited_and_unknown_units(self):
        for units,maximum in [("MB","unlimited"),("unknown","100")]:
            self.assertFalse(quota_summary({"result":{"status":1,"data":[{"id":"diskusage","units":units,"count":"5","max":maximum}]}})["recognized"])
    def test_over_quota(self):
        out=quota_summary({"result":{"status":1,"data":[{"id":"diskusage","units":"MB","count":"300","max":"200"}]}})
        self.assertEqual(out["reported_remaining"],"0")
