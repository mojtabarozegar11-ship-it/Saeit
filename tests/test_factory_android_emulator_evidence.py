"""Reject false device-approval, mismatched APK, or mismatched emulator screen."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import unittest
import zipfile

SCRIPT=Path(__file__).resolve().parents[1]/"scripts"/"factory_six_native_candidate_bundle.py"
spec=importlib.util.spec_from_file_location("factory_android_native_bundle",str(SCRIPT))
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

def zipper(members):
    out=io.BytesIO()
    with zipfile.ZipFile(out,"w",zipfile.ZIP_DEFLATED) as z:
        for name,raw in members.items():
            z.writestr(name,raw)
    return out.getvalue()

class RealAndroidReceiptTests(unittest.TestCase):
    def setUp(self):
        self.apk=zipper({
            "AndroidManifest.xml":b"manifest","classes.dex":b"dex",
            "assets/index.html":b"real offline game"})
        self.aab=zipper({
            "base/manifest/AndroidManifest.xml":b"manifest",
            "base/dex/classes.dex":b"dex",
            "base/assets/index.html":b"app"})
        self.screen=b"\x89PNG\r\n\x1a\n"+b"pixels"*900
        self.payload={
            "schema":"saeit.factory.android-emulated-runtime-check.v1",
            "family":"F12","package":"com.zomorodmelal.factory.f12",
            "android_sdk":35,"virtual_device":True,
            "actual_install_verified":True,"actual_activity_start_verified":True,
            "real_emulated_touch_and_swipe_dispatched":True,
            "app_alive_after_interaction":True,"no_app_fatal_crash_observed":True,
            "physical_device_tested":False,"independent_professional_review":False,
            "release_signing_verified":False,"quality_1000_certified":False,
            "commercial_release":False,
            "apk_sha256":hashlib.sha256(self.apk).hexdigest(),
            "screenshot_sha256":hashlib.sha256(self.screen).hexdigest(),
            "emulator_screen_size_bytes":len(self.screen),
            "distinct_screen_colors":28
        }

    def members(self):
        return {
            "app-debug.apk":self.apk,"app-debug.aab":self.aab,
            "emulator-proof.json":json.dumps(self.payload).encode(),
            "emulator-screen.png":self.screen,
        }

    def test_approved_only_as_emulator_technical_evidence(self):
        self.assertTrue(module.actual_format_integrity("F12",self.members()))

    def test_mismatched_real_apk_fails(self):
        members=self.members()
        members["app-debug.apk"]=self.apk+b"TAMPER"
        with self.assertRaisesRegex(RuntimeError,"MISMATCHED_EMULATOR"):
            module.actual_format_integrity("F12",members)

    def test_false_physical_and_release_claims_fail(self):
        for field in ("physical_device_tested","release_signing_verified",
                      "quality_1000_certified","commercial_release",
                      "independent_professional_review"):
            with self.subTest(field=field):
                self.payload[field]=True
                with self.assertRaisesRegex(RuntimeError,"MISMATCHED_EMULATOR"):
                    module.actual_format_integrity("F12",self.members())
                self.payload[field]=False

    def test_tampered_screenshot_fails(self):
        members=self.members()
        members["emulator-screen.png"]=self.screen+b"tampered"
        with self.assertRaisesRegex(RuntimeError,"MISMATCHED_EMULATOR"):
            module.actual_format_integrity("F12",members)

    def test_missing_half_of_evidence_fails(self):
        members=self.members()
        del members["emulator-screen.png"]
        with self.assertRaisesRegex(RuntimeError,"UNPAIRED_EMULATOR"):
            module.actual_format_integrity("F12",members)

if __name__=="__main__":
    unittest.main()
