"""Normalize site-local Zomorod roster; never infer task execution."""
from datetime import datetime, timezone
import unittest

from core import mojtaba_site_telemetry as telemetry
from core import mojtaba_site_fleet as fleet


def sample():
    return {
        "state": "source_registry_snapshot_only",
        "read_only_immutable": True,
        "database_state_proves_live_workers": False,
        "known_roles_found": 11,
        "unknown_code_records": 0,
        "agent_roles": [
            {"code": role, "enabled": True}
            for role in fleet.ZM_ROUTES
        ],
        "run_status_counts": {"ok": 644, "error": 6},
    }


class ZomorodRegistryTests(unittest.TestCase):
    def test_exact_known_site_roster_is_not_live_execution(self):
        t = datetime.now(timezone.utc)
        data = telemetry.normalize_zomorod_registry(
            sample(), captured_at_utc=t.isoformat(), now=t)
        self.assertEqual(data["known_roles_observed"], 11)
        self.assertEqual(data["enabled_role_records"], 11)
        self.assertTrue(data["registry_complete"])
        self.assertFalse(data["legacy_retirement_approved"])
        self.assertEqual(data["actual_worker_executions_verified_by_import"], 0)

    def test_unknown_roles_do_not_become_automatically_managed(self):
        t = datetime.now(timezone.utc)
        raw = sample()
        raw["unknown_code_records"] = 1
        data = telemetry.normalize_zomorod_registry(
            raw, captured_at_utc=t.isoformat(), now=t)
        self.assertFalse(data["registry_complete"])

    def test_reject_duplicate_roles(self):
        t = datetime.now(timezone.utc)
        raw = sample()
        raw["agent_roles"][1] = raw["agent_roles"][0]
        with self.assertRaises(fleet.SiteFleetError):
            telemetry.normalize_zomorod_registry(
                raw, captured_at_utc=t.isoformat(), now=t)

    def test_reject_non_boolean_enabled(self):
        t = datetime.now(timezone.utc)
        raw = sample()
        raw["agent_roles"][0]["enabled"] = "true"
        with self.assertRaises(fleet.SiteFleetError):
            telemetry.normalize_zomorod_registry(
                raw, captured_at_utc=t.isoformat(), now=t)

    def test_unobserved_or_writeable_database_rejected(self):
        t = datetime.now(timezone.utc)
        for field, bad in (("state", "unknown_not_observed"),
                           ("read_only_immutable", False),
                           ("database_state_proves_live_workers", True)):
            raw = sample()
            raw[field] = bad
            with self.subTest(field=field):
                with self.assertRaises(fleet.SiteFleetError):
                    telemetry.normalize_zomorod_registry(
                        raw, captured_at_utc=t.isoformat(), now=t)


if __name__ == "__main__":
    unittest.main()
