"""Security regression for the canonical bot's synthetic Android lab."""
import base64
from io import BytesIO
import json
import unittest
from zipfile import ZipFile

from ava_core.android_security_lab import NAME, security_lab_capability
from ava_core.capabilities import ActionRequest, CapabilityHub


class OwnerAndroidSecurityLabTests(unittest.TestCase):
    def setUp(self):
        self.hub = CapabilityHub(owner_id="agent-training-001")
        self.hub.register(*security_lab_capability())
        self.counter = 0

    def call(self, operation, data=None):
        self.counter += 1
        req = ActionRequest(
            "lab-" + str(self.counter), self.hub.owner_id,
            NAME, operation, data or {},
        )
        receipt = self.hub.execute(req)
        self.assertTrue(receipt.result.success)
        self.assertEqual(receipt.effect, "local")
        return json.loads(receipt.result.detail)

    def test_status_cannot_connect_to_real_devices(self):
        data = self.call("status")
        self.assertFalse(data["device_connection"])
        self.assertFalse(data["remote_control"])
        self.assertFalse(data["real_message_collection"])
        self.assertEqual(data["network_requests"], 0)

    def test_authentication_is_synthetic_and_offline(self):
        result = self.call("simulate_authentication")
        self.assertTrue(result["synthetic_valid_accepted"])
        self.assertTrue(result["synthetic_wrong_rejected"])

    def test_export_has_only_fictional_message_records(self):
        result = self.call("export_synthetic_messages")
        self.assertTrue(result["synthetic"])
        self.assertEqual(len(result["messages"]), 3)
        self.assertTrue(all("TRAINING_ONLY" == row["sender"]
                            for row in result["messages"]))

    def test_owner_supplied_minimal_security_report(self):
        result = self.call("inspect_device_report", {
            "report": {"model": "SM-A920F", "security_patch": "2022-06-01"}
        })
        self.assertEqual(result["fields"]["model"], "SM-A920F")
        self.assertFalse(result["verified_against_device"])

    def test_no_contacts_messages_or_photo_paths_are_ingested(self):
        report = {
            "model": "SM-A920F",
            "contacts": [{"phone": "not-allowed"}],
            "messages": ["not-allowed"],
            "photo_paths": ["/private/photo.jpg"],
        }
        result = self.call("inspect_device_report", {"report": report})
        self.assertEqual(result["fields"], {"model": "SM-A920F"})
        self.assertNotIn("not-allowed", json.dumps(result))
        self.assertNotIn("photo.jpg", json.dumps(result))

    def test_real_owner_supplied_apk_zip_is_not_executed(self):
        memory = BytesIO()
        xml = (
            '<manifest xmlns:android="http://schemas.android.com/apk/res/android">'
            '<uses-permission android:name="android.permission.READ_SMS"/>'
            '<uses-permission android:name="android.permission.ACCESS_FINE_LOCATION"/>'
            '</manifest>'
        )
        with ZipFile(memory, "w") as archive:
            archive.writestr("AndroidManifest.xml", xml)
        result = self.call("triage_apk", {
            "apk_base64": base64.b64encode(memory.getvalue()).decode("ascii")
        })
        self.assertFalse(result["executed_apk"])
        self.assertEqual(result["network_requests"], 0)
        self.assertIn("android.permission.READ_SMS", result["detected_permissions"])
        self.assertIn("android.permission.ACCESS_FINE_LOCATION", result["detected_permissions"])
        self.assertFalse(result["permissions_analysis_complete"])

    def test_binary_manifest_is_explicitly_incomplete(self):
        memory = BytesIO()
        with ZipFile(memory, "w") as archive:
            archive.writestr("AndroidManifest.xml", b"\x03\x00\x08\x00")
        result = self.call("triage_apk", {
            "apk_base64": base64.b64encode(memory.getvalue()).decode("ascii")
        })
        self.assertEqual(result["manifest_format"], "compiled_xml_not_parsed")
        self.assertFalse(result["permissions_analysis_complete"])

    def test_rejects_malformed_or_too_large_payloads(self):
        for value in ("!", "", "A" * 12_000_001):
            with self.subTest(value_size=len(value)), self.assertRaises(ValueError):
                self.call("triage_apk", {"apk_base64": value})

    def test_cannot_request_remote_control_or_real_sms_export(self):
        for operation in ("remote_control", "read_sms", "read_photos",
                          "install_spyware", "scan_device"):
            with self.subTest(operation=operation), self.assertRaises(ValueError):
                self.call(operation)

    def test_cross_owner_and_request_replay_denied(self):
        foreign = ActionRequest("other", "agent-foreign", NAME, "status", {})
        with self.assertRaises(PermissionError):
            self.hub.execute(foreign)
        req = ActionRequest("replay", self.hub.owner_id, NAME, "status", {})
        self.hub.execute(req)
        with self.assertRaises(PermissionError):
            self.hub.execute(req)


if __name__ == "__main__":
    unittest.main()
