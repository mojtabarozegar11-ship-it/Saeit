import datetime as dt
import unittest
from scripts.f01_offhost_transfer_admission_20261030 import decide

NOW=dt.datetime(2026,10,30,1,0,tzinfo=dt.timezone.utc)
def sufficient():
    return {
        "observed_utc":(NOW-dt.timedelta(minutes=5)).isoformat(),
        "cpu_count":3,"load1":1.0,"source_unprivileged_free_bytes":2*1024**3,
        "snapshot":{"bytes":1400000000,
                    "mtime_utc":(NOW-dt.timedelta(hours=1)).isoformat(),
                    "sqlite_consistency_verified":True},
        "recipient_public_key_matches_offline_recovery_key":True,
        "owner_recovery_key_custody_outside_chat":True,
        "transfer_path_encrypted_only":True,
        "destination":{"available_bytes":4*1024**3,"source":"GOOGLE_ACCOUNT_QUOTA_AUTHENTICATED"},
        "authorized_maintenance_and_io_window":True,
    }

class AdmissionTests(unittest.TestCase):
    def test_all_claims_still_manual_review(self):
        result=decide(sufficient(),NOW)
        self.assertEqual(result["status"],"ALLOW_FOR_MANUAL_REVIEW_ONLY")
        self.assertFalse(result["transfer_performed"])
        self.assertFalse(result["reboot_authorized"])
    def test_critical_gate_failures(self):
        x=sufficient()
        x["load1"]=128.06
        x["source_unprivileged_free_bytes"]=0
        x["destination"]={"available_bytes":None,"source":"SHARED_FILESYSTEM_ONLY"}
        x["owner_recovery_key_custody_outside_chat"]=False
        x["snapshot"]["mtime_utc"]=(NOW-dt.timedelta(days=2)).isoformat()
        r=decide(x,NOW)
        self.assertEqual(r["status"],"NO_GO")
        self.assertTrue({"SOURCE_LOAD_NOT_SAFE","SOURCE_HEADROOM_NOT_SAFE",
                         "OFFHOST_AVAILABLE_QUOTA_NOT_VERIFIED",
                         "OFFLINE_RECOVERY_CUSTODY_NOT_CONFIRMED",
                         "CURRENT_SNAPSHOT_REQUIRED"}.issubset(set(r["reasons"])))
    def test_no_fabricated_evidence(self):
        r=decide({},NOW)
        self.assertEqual(r["status"],"NO_GO")
        self.assertGreaterEqual(len(r["reasons"]),8)
    def test_stale_and_future_observation_fail(self):
        x=sufficient()
        x["observed_utc"]=(NOW+dt.timedelta(minutes=1)).isoformat()
        self.assertIn("FRESH_SOURCE_EVIDENCE_REQUIRED",decide(x,NOW)["reasons"])
        x["observed_utc"]=(NOW-dt.timedelta(hours=2)).isoformat()
        self.assertIn("FRESH_SOURCE_EVIDENCE_REQUIRED",decide(x,NOW)["reasons"])
    def test_invalid_quota_and_size_fail(self):
        x=sufficient()
        x["destination"]["available_bytes"]=1400000000
        x["snapshot"]["sqlite_consistency_verified"]=False
        self.assertIn("OFFHOST_AVAILABLE_QUOTA_NOT_VERIFIED",decide(x,NOW)["reasons"])
        self.assertIn("SQLITE_CONSISTENCY_NOT_PROVEN",decide(x,NOW)["reasons"])

if __name__=="__main__":
    unittest.main()
