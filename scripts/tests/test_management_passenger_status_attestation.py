"""Fail-closed checks for Passenger XML-to-live-Python identity binding."""

import unittest

from scripts.management_passenger_status_attestation import APP_ROOT, attest_xml


def status_xml(root=APP_ROOT, python="/home/zomorod2/Saeit/.venv/bin/python", pids=(1911,)):
    process_nodes = "".join(f"<process><pid>{pid}</pid></process>" for pid in pids)
    return (
        f"<info><supergroups><supergroup><group>"
        f"<app_root>{root}</app_root>"
        f"<options><python>{python}</python></options>"
        f"<processes>{process_nodes}</processes>"
        f"</group></supergroup></supergroups></info>"
    ).encode("utf-8")


def fake_configured(_path):
    return 111, 222


def fake_process(_pid):
    return 1001, (111, 222), "3.11"


class PassengerStatusAttestationTests(unittest.TestCase):
    def audit(self, xml, **overrides):
        return attest_xml(xml, configured_binary=overrides.get("configured_binary", fake_configured),
                          process_binary=overrides.get("process_binary", fake_process),
                          expected_uid=1001)

    def test_exact_live_process_matches_configuration(self):
        result = self.audit(status_xml())
        self.assertTrue(result["active_interpreter_binary_attested"])
        self.assertEqual(result["matching_application_processes"], 1)
        self.assertEqual(result["python_version_hint"], "3.11")
        self.assertFalse(result["release_permitted"])
        self.assertFalse(result["migrations_attested"])

    def test_other_app_cannot_attest_target(self):
        result = self.audit(status_xml(root="/home/zomorod2/Other"))
        self.assertEqual(result["reason"], "target_app_missing_or_ambiguous")
        self.assertFalse(result["active_interpreter_binary_attested"])

    def test_second_matching_app_group_is_ambiguous(self):
        inner = status_xml().decode().replace("<info><supergroups>", "").replace("</supergroups></info>", "")
        xml = f"<info><supergroups>{inner}{inner}</supergroups></info>".encode()
        self.assertEqual(self.audit(xml)["reason"], "target_app_missing_or_ambiguous")

    def test_configured_path_without_worker_does_not_attest(self):
        self.assertEqual(self.audit(status_xml(pids=()))["reason"], "no_live_passenger_process")

    def test_other_executable_never_matches(self):
        result = self.audit(status_xml(), process_binary=lambda pid: (1001, (111, 333), "3.11"))
        self.assertEqual(result["reason"], "configured_python_differs_from_live_process")

    def test_foreign_uid_never_matches(self):
        result = self.audit(status_xml(), process_binary=lambda pid: (2002, (111, 222), "3.11"))
        self.assertEqual(result["reason"], "foreign_uid_process")

    def test_duplicate_pid_denied(self):
        self.assertEqual(self.audit(status_xml(pids=(1911, 1911)))["reason"], "duplicate_passenger_pid")

    def test_malformed_xml_denied(self):
        self.assertEqual(self.audit(b"<info>")["reason"], "invalid_passenger_xml")

    def test_relative_configured_python_denied(self):
        result = self.audit(status_xml(python="python"), configured_binary=lambda p: (_ for _ in ()).throw(ValueError()))
        self.assertEqual(result["reason"], "configured_binary_not_identified")

    def test_unreadable_live_worker_denied(self):
        result = self.audit(status_xml(), process_binary=lambda pid: (_ for _ in ()).throw(OSError()))
        self.assertEqual(result["reason"], "passenger_process_unreadable")

    def test_oversized_status_denied(self):
        self.assertEqual(self.audit(b"x" * (2 * 1024 * 1024 + 1))["reason"], "status_xml_empty_or_oversized")


if __name__ == "__main__":
    unittest.main()
