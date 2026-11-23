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
        self.hub = CapabilityHub(owner_id="agent-training-001",
                                 authorize=lambda owner, request, operation: owner == request.owner_id)
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
        self.assertEqual(receipt.effect, "read")
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


    def test_training_course_lists_only_synthetic_lessons(self):
        result = self.call("training_lessons")
        self.assertTrue(result["synthetic"])
        self.assertEqual(len(result["lessons"]), 4)
        self.assertEqual(result["network_requests"], 0)
        self.assertFalse(result["remote_access"])
        self.assertFalse(result["real_data_collected"])

    def test_training_cases_have_distinct_expected_risk_levels(self):
        for case_id, expected in (
            ("normal_notes", "low"),
            ("overprivileged_app", "high"),
            ("fictional_transfer", "high"),
            ("fictional_covert_surveillance", "high"),
        ):
            with self.subTest(case=case_id):
                result = self.call("training_case", {"case_id": case_id})
                self.assertEqual(result["risk_level"], expected)
                self.assertTrue(result["fictional"])
                self.assertEqual(result["network_requests"], 0)
                self.assertFalse(result["actual_compromise_detected"])

    def test_training_quiz_presents_then_grades_answers(self):
        for lesson_id, answer in (
            ("android_permissions", "B"),
            ("accessibility_misuse", "A"),
            ("synthetic_exfiltration", "C"),
            ("covert_surveillance_detection", "A"),
        ):
            with self.subTest(lesson=lesson_id):
                prompt = self.call("training_quiz", {"lesson_id": lesson_id})
                self.assertEqual(set(prompt["options"]), {"A", "B", "C"})
                self.assertNotIn("correct_choice", prompt)
                graded = self.call("training_quiz", {
                    "lesson_id": lesson_id, "choice": answer,
                })
                self.assertTrue(graded["correct"])
                incorrect = self.call("training_quiz", {
                    "lesson_id": lesson_id, "choice": "B" if answer != "B" else "A",
                })
                self.assertFalse(incorrect["correct"])

    def test_training_rejects_unrecognized_cases_and_nonchoices(self):
        for args in ({}, {"case_id": "any-other-phone"}, {"case_id": ["normal_notes"]}):
            with self.subTest(args=args), self.assertRaises(ValueError):
                self.call("training_case", args)
        for args in (
            {"lesson_id": "private_chat"},
            {"lesson_id": "android_permissions", "choice": "run_payload"},
            {"lesson_id": "android_permissions", "choice": ["A"]},
        ):
            with self.subTest(args=args), self.assertRaises(ValueError):
                self.call("training_quiz", args)

    def test_training_outputs_cannot_expose_external_device_content(self):
        for operation, args in (
            ("training_lessons", {}),
            ("training_case", {"case_id": "fictional_transfer"}),
            ("training_case", {"case_id": "fictional_covert_surveillance"}),
            ("training_quiz", {"lesson_id": "synthetic_exfiltration"}),
            ("training_quiz", {"lesson_id": "covert_surveillance_detection"}),
        ):
            response = json.dumps(self.call(operation, args))
            self.assertNotIn("https://", response)
            self.assertNotIn("READ_REAL_SMS", response)
            self.assertNotIn("REMOTE_CONTROL", response)

    def test_covert_surveillance_scenario_has_no_real_collection_or_access(self):
        report = self.call("training_case", {"case_id": "fictional_covert_surveillance"})
        self.assertEqual(report["risk_level"], "high")
        self.assertTrue(report["fictional"])
        self.assertEqual(report["network_requests"], 0)
        self.assertFalse(report["actual_compromise_detected"])
        serialized = json.dumps(report)
        self.assertIn("SIMULATED_READ_DEMO_MEDIA_NO_FILES", serialized)
        self.assertIn("SIMULATED_DATA_TRANSFER_NO_NETWORK", serialized)
        for private_operation in ("read_sms", "read_photos", "remote_control", "install_spyware"):
            with self.subTest(operation=private_operation), self.assertRaises(ValueError):
                self.call(private_operation)



if __name__ == "__main__":
    unittest.main()
