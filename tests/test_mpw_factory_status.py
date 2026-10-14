"""VPS telemetry validity tests: missing/stale/invalid must fail closed."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import os
import tempfile
from unittest.mock import patch
from django.test import SimpleTestCase
from command_center.factory_status import read_factory_status

class FactoryStatusTests(SimpleTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.file=Path(self.temp.name)/"status.json"
        self.patch=patch("command_center.factory_status.STATUS_FILE",self.file)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def fixture(self, when=None):
        now=when or datetime.now(timezone.utc)
        return {
            "schema_version":1,"source":"saeit_verified_ssh_vps_sampler",
            "observed_at":now.isoformat(),"loop_pid_verified":True,
            "activity_log_age_seconds":38,
            "product_cycle":{"built_product_count":2,"publishable_product_count":0,
                "artifact_qa_passed":True,"store_distribution_state":"not_connected",
                "age_seconds":2500},
        }

    def write(self, value):
        self.file.write_text(json.dumps(value))
        self.file.chmod(0o600)

    def test_missing_and_malformed_stay_unknown(self):
        self.assertEqual(read_factory_status()["state"],"unknown")
        self.file.write_text("NOT JSON")
        self.file.chmod(0o600)
        self.assertEqual(read_factory_status()["state"],"unknown")

    def test_fresh_verified_running_not_claiming_revenue(self):
        self.write(self.fixture())
        result=read_factory_status()
        self.assertEqual(result["state"],"observed_running")
        self.assertEqual(result["product_cycle"]["built_product_count"],2)
        self.assertEqual(result["product_cycle"]["publishable_product_count"],0)
        self.assertFalse(result["commercial_revenue_verified"])

    def test_stale_and_bad_source_rejected(self):
        self.write(self.fixture(datetime.now(timezone.utc)-timedelta(hours=3)))
        self.assertEqual(read_factory_status()["state"],"stale")
        x=self.fixture()
        x["source"]="untrusted"
        self.write(x)
        self.assertEqual(read_factory_status()["state"],"unknown")

    def test_invalid_permissions_and_data_rejected(self):
        self.write(self.fixture())
        self.file.chmod(0o644)
        self.assertEqual(read_factory_status()["state"],"unknown")
        bad=self.fixture()
        bad["loop_pid_verified"]="yes"
        self.write(bad)
        self.assertEqual(read_factory_status()["state"],"unknown")
