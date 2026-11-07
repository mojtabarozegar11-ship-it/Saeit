"""Prevent false-positive cPanel receipts from allowlisted no-op cases."""
import pathlib
import re
import unittest


BRIDGE = pathlib.Path(__file__).resolve().parents[2] / "deploy/cpanel_direct_command.sh"
WORKFLOW = pathlib.Path(__file__).resolve().parents[2] / ".github/workflows/management-ledger-cpanel-readonly-receipt-20261107.yml"


class ManagementBridgeRouteContractTests(unittest.TestCase):
    def test_runtime_probe_has_a_real_dispatch_case(self):
        source = BRIDGE.read_text(encoding="utf-8")
        self.assertIn("runtime_python_candidates|management_runtime_fingerprint|management_domain_docroot) ;;", source)
        self.assertRegex(source, re.compile(
            r"(?m)^  management_runtime_fingerprint\)\n"
            r"(?:[^\n]*\n)*?"
            r"[^\n]*< scripts/cpanel_management_runtime_probe\.sh\n"
            r"    ;;$"
        ))

    def test_unattested_django_operations_fail_explicitly(self):
        source = BRIDGE.read_text(encoding="utf-8")
        self.assertIn("  django_check|django_migrations)", source)
        self.assertIn("CPANEL_DJANGO_PROBE_BLOCKED_UNATTESTED_ACTIVE_INTERPRETER", source)
        self.assertNotIn("/virtualenv/Saeit/3.11/bin/python;", source)

    def test_workflow_demands_runtime_receipt(self):
        source = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("MANAGEMENT_RUNTIME_RECEIPT_MISSING_OR_INVALID", source)
        self.assertIn("grep -qx 'RECEIPT_CLASS=MANAGEMENT_RUNTIME_READONLY_V1'", source)
        self.assertIn("PASSENGER_PYTHON_[A-Z_]+", source)

    def test_identity_probe_never_executes_configured_python(self):
        probe = (BRIDGE.parents[1] / "scripts/cpanel_management_runtime_probe.sh").read_text(encoding="utf-8")
        self.assertIn("PASSENGER_PYTHON_RESOLVED_VERSION_HINT_", probe)
        self.assertIn("PASSENGER_PYTHON_BINARY_MATCH_", probe)
        self.assertIn("readlink -f --", probe)
        self.assertIn("stat -Lc '%d:%i'", probe)


if __name__ == "__main__":
    unittest.main()
