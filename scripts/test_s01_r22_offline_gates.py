"""No network, no production host, no database. Synthetic isolated fixtures only."""
import hashlib
import io
import json
import os
import sys
from contextlib import redirect_stdout
from datetime import datetime, timezone
from unittest.mock import patch
from pathlib import Path
import tarfile
import tempfile
import unittest
from scripts.s01_r22_offline_gates import (checkout, game_source_gate, office_stage,
                                            public_route_contract, regular_bytes,
                                            release_readiness_contract, main)

class R22Tests(unittest.TestCase):
    def files(self, root, old=b"x=1\n", new=b"x=1\n"):
        a, b = Path(root)/"approved.py", Path(root)/"observed.py"
        a.write_bytes(old); b.write_bytes(new)
        return a, b, hashlib.sha256(old).hexdigest()

    def stage(self, root):
        root = Path(root); code = root/"code"
        files = {"config/settings.py": b"DEBUG=False\n", "company_messaging/models.py": b"class X: pass\n"}
        with tarfile.open(root/"package.tar", "w") as tf:
            for name, data in files.items():
                member = tarfile.TarInfo(name); member.size=len(data)
                tf.addfile(member, io.BytesIO(data))
                p=code/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
        return hashlib.sha256((root/"package.tar").read_bytes()).hexdigest(), code

    def test_checkout_identical(self):
        with tempfile.TemporaryDirectory() as d:
            a,b,pin=self.files(d)
            self.assertEqual(checkout(str(b),str(a),pin)["status"],"PIN_MATCH")

    def test_checkout_format_only(self):
        with tempfile.TemporaryDirectory() as d:
            a,b,pin=self.files(d,new=b"x = 1  # comment\n")
            self.assertEqual(checkout(str(b),str(a),pin)["status"],"FORMAT_ONLY_DRIFT")

    def test_checkout_semantic_delta(self):
        with tempfile.TemporaryDirectory() as d:
            a,b,pin=self.files(d,new=b"x=2\n")
            result=checkout(str(b),str(a),pin)
            self.assertEqual(result["status"],"SEMANTIC_DRIFT")
            self.assertEqual(result["top_level_change_count"],1)
            self.assertNotIn("x=2",str(result))

    def test_checkout_pin_reject(self):
        with tempfile.TemporaryDirectory() as d:
            a,b,pin=self.files(d)
            with self.assertRaisesRegex(ValueError,"PIN_MISMATCH"):
                checkout(str(b),str(a),"0"*64)

    def test_checkout_syntax_reject(self):
        with tempfile.TemporaryDirectory() as d:
            a,b,pin=self.files(d,new=b"def bad(:\n")
            with self.assertRaisesRegex(ValueError,"SYNTAX_INVALID"):
                checkout(str(b),str(a),pin)

    def test_intermediate_symlink_reject(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/"real").mkdir();(root/"real"/"a.py").write_text("x=1")
            (root/"alias").symlink_to(root/"real",target_is_directory=True)
            with self.assertRaises(OSError):regular_bytes(str(root/"alias"/"a.py"))

    def test_hardlink_reject(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);p=root/"a.py";p.write_text("x=1");os.link(p,root/"b.py")
            with self.assertRaisesRegex(ValueError,"UNSAFE_SOURCE_FILE"):
                regular_bytes(str(p))

    def test_stage_valid(self):
        with tempfile.TemporaryDirectory() as d:
            pin,code=self.stage(d)
            self.assertEqual(office_stage(d,pin)["verified_file_count"],2)

    def test_stage_mutated_file(self):
        with tempfile.TemporaryDirectory() as d:
            pin,code=self.stage(d);(code/"config/settings.py").write_text("DEBUG=True")
            with self.assertRaisesRegex(ValueError,"MISMATCH"):
                office_stage(d,pin)

    def test_stage_unarchived_executable(self):
        with tempfile.TemporaryDirectory() as d:
            pin,code=self.stage(d);(code/"config/extra.py").write_text("x=1")
            with self.assertRaisesRegex(ValueError,"UNARCHIVED_EXECUTABLE"):
                office_stage(d,pin)

    def test_stage_symlink(self):
        with tempfile.TemporaryDirectory() as d:
            pin,code=self.stage(d);p=code/"config/settings.py";p.unlink();p.symlink_to(code/"company_messaging/models.py")
            with self.assertRaisesRegex(ValueError,"STAGE_SYMLINK"):
                office_stage(d,pin)

    def test_stage_special_member(self):
        with tempfile.TemporaryDirectory() as d:
            pin,code=self.stage(d)
            with tarfile.open(Path(d)/"package.tar","a") as tf:
                m=tarfile.TarInfo("config/link.py");m.type=tarfile.SYMTYPE;m.linkname="settings.py";tf.addfile(m)
            pin=hashlib.sha256((Path(d)/"package.tar").read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError,"ARCHIVE_SPECIAL_MEMBER"):
                office_stage(d,pin)

    def test_public_route_blocked_baseline(self):
        d={"source":"READ_ONLY_HTTP_OBSERVATION","origin":"https://zomorodmelal.ir",
           "observed_at":"2026-10-31T04:00Z",
           "routes":{p:{"status":s,"redirected":False} for p,s in [("/",200),("/api/health/",200),
                ("/company/office/messages/",404),("/company/office/marketing/",404)]}}
        now=datetime(2026,10,31,4,5,tzinfo=timezone.utc)
        self.assertEqual(public_route_contract(d,now=now)["status"],"BLOCKED_BASELINE_RECORDED")
        d["routes"]["/company/office/messages/"]["status"]=200
        self.assertEqual(public_route_contract(d,now=now)["status"],"NEEDS_REVIEW")

    def test_public_route_fake_source_rejected(self):
        with self.assertRaisesRegex(ValueError,"INVALID_OBSERVATION_FORMAT"):
            public_route_contract({"source":"CLAIM","routes":{}})

    def test_game_source_policy_off(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);game=root/"game.js";policy=root/"policy.mjs"
            game.write_text("function nextMission(){} function resumeInMemoryCampaign(){} canEnterGameplay(")
            policy.write_text("ownerApproved: false, checkoutEnabled: false, verifiedBackend: false")
            result=game_source_gate(str(game),str(policy))
            self.assertEqual(result["status"],"SOURCE_GUARDS_PRESENT")
            self.assertFalse(result["browser_verified"])

    def test_game_source_policy_on(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);game=root/"game.js";policy=root/"policy.mjs"
            game.write_text("function nextMission(){} function resumeInMemoryCampaign(){} canEnterGameplay(")
            policy.write_text("ownerApproved: true, checkoutEnabled: false, verifiedBackend: false")
            self.assertEqual(game_source_gate(str(game),str(policy))["status"],"SOURCE_GUARD_MISSING")


    def test_stage_unarchived_html_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            pin, code = self.stage(d)
            extra = code / "company_messaging/templates/unarchived.html"
            extra.parent.mkdir(parents=True, exist_ok=True)
            extra.write_text("<script>unexpected()</script>")
            with self.assertRaisesRegex(ValueError, "UNARCHIVED_ASSET"):
                office_stage(d, pin)

    def test_stage_unarchived_javascript_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            pin, code = self.stage(d)
            extra = code / "company_messaging/static/unarchived.js"
            extra.parent.mkdir(parents=True, exist_ok=True)
            extra.write_text("console.log('unexpected')")
            with self.assertRaisesRegex(ValueError, "UNARCHIVED_ASSET"):
                office_stage(d, pin)

    def test_stage_parent_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            real = root / "real"
            real.mkdir()
            pin, _ = self.stage(real)
            (root / "alias").symlink_to(real, target_is_directory=True)
            with self.assertRaises(OSError):
                office_stage(str(root / "alias"), pin)

    def test_public_route_stale_and_wrong_origin_rejected(self):
        evidence = {"source":"READ_ONLY_HTTP_OBSERVATION",
                    "origin":"https://zomorodmelal.ir",
                    "observed_at":"2026-10-31T04:00:00Z",
                    "routes":{}}
        now = datetime(2026, 10, 31, 5, 0, tzinfo=timezone.utc)
        with self.assertRaisesRegex(ValueError, "OBSERVATION_STALE"):
            public_route_contract(evidence, now=now)
        evidence["origin"] = "https://unexpected.example"
        with self.assertRaisesRegex(ValueError, "INVALID_OBSERVATION_ORIGIN"):
            public_route_contract(evidence, now=now)

    def test_public_route_redirect_evidence_required(self):
        evidence = {"source":"READ_ONLY_HTTP_OBSERVATION",
                    "origin":"https://zomorodmelal.ir",
                    "observed_at":"2026-10-31T04:00:00Z",
                    "routes":{p:{"status":s} for p,s in
                        [("/",200),("/api/health/",200),
                         ("/company/office/messages/",404),("/company/office/marketing/",404)]}}
        now = datetime(2026, 10, 31, 4, 1, tzinfo=timezone.utc)
        self.assertEqual(public_route_contract(evidence, now=now)["status"], "NEEDS_REVIEW")

    def test_format_only_drift_cli_cannot_pass_gate(self):
        with tempfile.TemporaryDirectory() as d:
            approved, observed, pin = self.files(d, new=b"x = 1  # harmless comment\n")
            out = io.StringIO()
            with patch.object(sys, "argv", ["offline", "checkout",
                              "--approved", str(approved), "--current", str(observed),
                              "--sha256", pin]), redirect_stdout(out):
                self.assertEqual(main(), 2)
            self.assertIn("FORMAT_ONLY_DRIFT", out.getvalue())

    def test_public_blocked_baseline_cli_cannot_pass_gate(self):
        with tempfile.TemporaryDirectory() as d:
            observation = {"source":"READ_ONLY_HTTP_OBSERVATION",
                           "origin":"https://zomorodmelal.ir",
                           "observed_at":datetime.now(timezone.utc).isoformat(),
                           "routes":{p:{"status":s,"redirected":False} for p,s in
                             [("/",200),("/api/health/",200),
                              ("/company/office/messages/",404),("/company/office/marketing/",404)]}}
            path = Path(d) / "observation.json"
            path.write_text(json.dumps(observation))
            out = io.StringIO()
            with patch.object(sys, "argv", ["offline", "public-routes", "--evidence", str(path)]), redirect_stdout(out):
                self.assertEqual(main(), 2)
            self.assertIn("BLOCKED_BASELINE_RECORDED", out.getvalue())

    def test_missing_release_evidence_remains_blocked(self):
        result = release_readiness_contract({"source_sha_reconciled":True})
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("passenger_db_authority_verified", result["missing"])
        self.assertIn("durable_offhost_full_restore_verified", result["missing"])
        self.assertIn("rollback_rehearsal_verified", result["missing"])
        self.assertIn("buyer_flow_accepted", result["missing"])
        self.assertFalse(result["release_permitted"])

    def test_self_declared_complete_release_evidence_never_authorizes(self):
        from scripts.s01_r22_offline_gates import REQUIRED_RELEASE_EVIDENCE
        result = release_readiness_contract({name:True for name in REQUIRED_RELEASE_EVIDENCE})
        self.assertEqual(result["status"], "INDEPENDENT_ATTESTATION_REQUIRED")
        self.assertEqual(result["missing"], [])
        self.assertFalse(result["safe_to_deploy"])
        self.assertFalse(result["release_permitted"])

if __name__ == "__main__": unittest.main()
