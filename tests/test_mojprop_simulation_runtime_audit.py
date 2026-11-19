import json
from io import StringIO
from django.core.management import call_command
from django.test import TestCase, override_settings
from prop_firm.models import PropSimulationAccount, PropPlan1Invoice

class SimulationRuntimeAuditTests(TestCase):
    @override_settings(MPW_SIMULATION_IDENTITY_ENABLED=False,
                       MPW_SIMULATION_CHECKOUT_ENABLED=False,
                       MPW_SIMULATION_RECIPIENT="not-a-public-receiving-address",
                       MPW_SIMULATION_EVENT_KEY="private-test-material-not-in-output")
    def test_audit_is_read_only_and_does_not_expose_configuration_secrets(self):
        out = StringIO()
        call_command("audit_simulation_runtime", stdout=out)
        report = json.loads(out.getvalue())
        self.assertTrue(report["latest_migration_recorded"])
        self.assertTrue(all(report["schema_columns_present"].values()))
        self.assertTrue(all(report["django_routes_resolve"].values()))
        self.assertFalse(report["configuration"]["checkout_enabled"])
        self.assertFalse(report["all_local_checks_pass"])
        self.assertFalse(report["commercial_release_verified"])
        self.assertNotIn("private-test-material", out.getvalue())
        self.assertNotIn("not-a-public-receiving-address", out.getvalue())
        self.assertEqual(PropSimulationAccount.objects.count(), 0)
        self.assertEqual(PropPlan1Invoice.objects.count(), 0)
