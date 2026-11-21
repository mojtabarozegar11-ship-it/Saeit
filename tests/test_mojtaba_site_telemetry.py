"""MojPlayWin telemetry registry migration is read-only and fail-closed."""
from datetime import datetime, timezone
import unittest

from core import mojtaba_site_fleet as fleet
from core import mojtaba_site_telemetry as telemetry

def fixture():
    items = []
    for ident in sorted(telemetry.EXPECTED_IDS):
        is_module = ident.startswith("module_")
        items.append({
            "id": ident, "state": "loaded_only" if is_module else "unknown",
            "source": "cpanel_private_report",
            "metrics": {"functional_execution_verified": False} if is_module else {},
        })
    return {"tenant": "mojplaywin-main", "source": "private_cpanel_reports",
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "items": items}


class TelemetryTests(unittest.TestCase):
    def test_103_slots_not_103_bots(self):
        data = telemetry.normalize_mpw_telemetry(fixture())
        self.assertEqual(data["declared_slots"], 103)
        self.assertEqual(data["module_loaded_only_slots"], 77)
        self.assertEqual(data["functional_executions_verified_by_import"], 0)
        self.assertFalse(data["migration_or_legacy_cleanup_approved"])
        self.assertFalse(data["source_is_cryptographically_authenticated"])

    def test_tenant_mismatch(self):
        data = fixture()
        data["tenant"] = "zomorodmelal"
        with self.assertRaises(fleet.SiteFleetError):
            telemetry.normalize_mpw_telemetry(data)

    def test_missing_and_duplicate_rejected(self):
        data = fixture()
        data["items"][-1] = data["items"][0]
        with self.assertRaises(fleet.SiteFleetError):
            telemetry.normalize_mpw_telemetry(data)
        data = fixture()
        data["items"].pop()
        with self.assertRaises(fleet.SiteFleetError):
            telemetry.normalize_mpw_telemetry(data)

    def test_fake_module_execution_rejected(self):
        data = fixture()
        mod = next(x for x in data["items"] if x["id"] == "module_1")
        mod["metrics"]["functional_execution_verified"] = True
        with self.assertRaises(fleet.SiteFleetError):
            telemetry.normalize_mpw_telemetry(data)

    def test_loaded_only_never_healthy(self):
        data = fixture()
        mod = next(x for x in data["items"] if x["id"] == "module_1")
        mod["state"] = "healthy"
        with self.assertRaises(fleet.SiteFleetError):
            telemetry.normalize_mpw_telemetry(data)

    def test_missing_private_source_rejected(self):
        data = fixture()
        data["source"] = "private_cpanel_unavailable"
        with self.assertRaises(fleet.SiteFleetError):
            telemetry.normalize_mpw_telemetry(data)


if __name__ == "__main__":
    unittest.main()
