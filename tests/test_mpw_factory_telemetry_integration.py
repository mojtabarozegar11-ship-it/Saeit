"""End-to-end local telemetry fixture: sampler -> bounded receiver -> staff reader.

Uses fake HOME and an isolated temporary filesystem. No server or credentials.
"""
import datetime
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

from tests.test_mpw_factory_telemetry_transport import SAMPLE, RECEIVE
from command_center import factory_status


class PrivateTelemetryIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home=Path(self.temp.name)
        ops=self.home/"factory-runtime/operations"
        ops.mkdir(parents=True)
        (ops/"vps-only-loop.sh").write_text("#!/bin/sh\n")
        (ops/"vps-only-loop.pid").write_text("99999999\n")
        (ops/"vps-only-factory.log").write_text("local fixture\n")
        product=self.home/"factory-runtime/private/autonomous-product-cycle"
        product.mkdir(parents=True)
        (product/"production-state.json").write_text(json.dumps({
            "mode":"autonomous_supply_led","depends_on_orders":False,
            "built_product_count":2,"publishable_product_count":0,
            "artifact_qa_passed":True,"store_distribution_state":"not_connected",
        }))

    def test_sampler_to_private_file_to_staff_reader(self):
        payload=SAMPLE.sample(home=self.home)
        self.assertFalse(payload["loop_pid_verified"])
        pipe=types.SimpleNamespace(buffer=io.BytesIO(json.dumps(payload).encode()))
        with patch("pwd.getpwuid",return_value=types.SimpleNamespace(pw_name="zomorod2")), \
             patch.object(Path,"home",return_value=self.home), \
             patch.object(sys,"stdin",pipe):
            RECEIVE.main()
        storage=self.home/".mpw-factory-status"
        file=storage/"status.json"
        self.assertEqual(storage.stat().st_mode & 0o777,0o700)
        self.assertEqual(file.stat().st_mode & 0o777,0o600)
        with patch.object(factory_status,"STATUS_FILE",file):
            data=factory_status.read_factory_status()
            self.assertEqual(data["state"],"not_recently_verified_running")
            self.assertEqual(data["product_cycle"]["built_product_count"],2)
            self.assertEqual(data["product_cycle"]["publishable_product_count"],0)
            self.assertFalse(data["commercial_revenue_verified"])
            past=datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(hours=3)
            self.assertEqual(factory_status.read_factory_status(now=past)["state"],"stale")

    def test_receiver_rejects_untrusted_input_without_new_file(self):
        value=SAMPLE.sample(home=self.home)
        value["source"]="forged_report"
        pipe=types.SimpleNamespace(buffer=io.BytesIO(json.dumps(value).encode()))
        with patch("pwd.getpwuid",return_value=types.SimpleNamespace(pw_name="zomorod2")), \
             patch.object(Path,"home",return_value=self.home), \
             patch.object(sys,"stdin",pipe):
            with self.assertRaises(ValueError):
                RECEIVE.main()
        self.assertFalse((self.home/".mpw-factory-status/status.json").exists())
