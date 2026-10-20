import hashlib
import importlib.util
import json
from pathlib import Path
import os
import tempfile
import unittest
from datetime import datetime,timezone

SCRIPT=Path(__file__).resolve().parents[1]/"scripts"/"factory_site_federation.py"
spec=importlib.util.spec_from_file_location("factory_site_federation",SCRIPT)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class FactorySiteFederationTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.heritage=self.root/"heritage"
        self.heritage.mkdir()
        self.output=self.root/"private"/"federation.json"
        self.snap=self.root/"snapshot.json"

    def snapshot(self,hashes=None):
        data={
          "schema":m.SCHEMA,"source":"private_cpanel_readonly",
          "observed_utc":datetime.now(timezone.utc).isoformat(timespec="seconds"),
          "zomorod_site_roles":[{"code":x,"enabled":True,"observed_run":True} for x in m.ROLES],
          "mojplaywin_master_gen64":"active_private",
          "mojplaywin_evolution_gen65":"gen65_operational_private",
          "module_slots":[{"slot":i+1,"module":"unverified_slot_"+str(i+1),"import_verified":i<5,
                           "functional_execution_verified":False} for i in range(77)],
          "robot_roles":[{"name":name,"group":5 if name in m.FIVE else 6,
                          "reported_status":"unknown"} for name in m.FIVE+m.SIX],
          "v91_source_files":hashes or [],
          "private_runtime_modified":False}
        self.snap.write_text(json.dumps(data))
        return data

    def test_missing_reports_fail_unknown_not_active(self):
        with tempfile.TemporaryDirectory() as td:
            d=m.collect_sites(td)
            self.assertEqual(len(d["module_slots"]),77)
            self.assertEqual(len(d["robot_roles"]),11)
            self.assertEqual(len(d["zomorod_site_roles"]),0)
            self.assertEqual(d["mojplaywin_evolution_gen65"],"unknown")
            self.assertFalse(d["private_runtime_modified"])

    def test_source_hash_matches_and_does_not_mark_execution(self):
        b=b"x=1\n"
        p=self.heritage/"health.py"
        p.write_bytes(b)
        self.snapshot([{"path":"health.py","sha256":hashlib.sha256(b).hexdigest(),"bytes":len(b)}])
        report=m.install_snapshot(self.snap,self.heritage,self.output)
        self.assertEqual(report["matched_site_source_count"],1)
        self.assertEqual(report["modules_import_receipt_claims"],5)
        self.assertEqual(report["modules_execution_verified_by_factory"],0)
        self.assertEqual(report["robots_execution_verified_by_factory"],0)
        self.assertFalse(report["all_77_live_in_factory"])
        self.assertEqual(self.output.stat().st_mode & 0o077,0)

    def test_changed_source_is_not_promoted(self):
        self.heritage.joinpath("health.py").write_text("x=2\n")
        self.snapshot([{"path":"health.py","sha256":"a"*64,"bytes":4}])
        report=m.install_snapshot(self.snap,self.heritage,self.output)
        self.assertEqual(report["matched_site_source_count"],0)
        self.assertEqual(report["source_mismatches"],["health.py"])

    def test_unverified_snapshot_rejected(self):
        d=self.snapshot()
        d["module_slots"]=d["module_slots"][:50]
        self.snap.write_text(json.dumps(d))
        with self.assertRaisesRegex(ValueError,"INVALID_77_MODULE_INVENTORY"):
            m.install_snapshot(self.snap,self.heritage,self.output)

    def test_unverified_source_names_rejected(self):
        self.snapshot([{"path":"../key.py","sha256":"a"*64,"bytes":42}])
        # Escape attempts must not be matched or executed.
        with self.assertRaisesRegex(ValueError, "UNSAFE_RELATIVE_SOURCE_PATH"):
            m.install_snapshot(self.snap,self.heritage,self.output)

if __name__=="__main__":
    unittest.main()
