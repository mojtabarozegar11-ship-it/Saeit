"""Local tests for the bounded factory sampler and cPanel receiver.

No network, real VPS, production file or active site is involved.
"""
import datetime
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import time
import unittest


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ROOT = Path(__file__).resolve().parents[1]
SAMPLE = load(ROOT/"scripts/mpw_factory_telemetry_sample.py", "telemetry_sample_test_module")
RECEIVE = load(ROOT/"scripts/mpw_factory_telemetry_receive.py", "telemetry_receive_test_module")


class FactorySamplerTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.home = Path(self.directory.name)
        self.base = self.home/"factory-runtime"
        self.ops = self.base/"operations"
        self.ops.mkdir(parents=True)
        self.private = self.base/"private/autonomous-product-cycle"
        self.private.mkdir(parents=True)
        self.script = self.ops/"vps-only-loop.sh"
        self.script.write_text("#!/bin/sh\nexit 0\n")
        self.pid = self.ops/"vps-only-loop.pid"
        self.pid.write_text("99999999\n")
        self.activity = self.ops/"vps-only-factory.log"
        self.activity.write_text("Testing fixture, not proof of activity\n")
        self.state = self.private/"production-state.json"
        self.state.write_text(json.dumps({
            "mode":"autonomous_supply_led",
            "depends_on_orders":False,
            "built_product_count":2,
            "publishable_product_count":0,
            "artifact_qa_passed":True,
            "store_distribution_state":"not_connected",
        }))

    def test_bounded_schema_and_no_false_runtime_assertion(self):
        result = SAMPLE.sample(home=self.home)
        self.assertEqual(result["schema_version"],1)
        self.assertEqual(result["source"],"saeit_verified_ssh_vps_sampler")
        self.assertEqual(result["product_cycle"]["built_product_count"],2)
        self.assertEqual(result["product_cycle"]["publishable_product_count"],0)
        self.assertIs(result["loop_pid_verified"],False)
        self.assertTrue(0 <= result["activity_log_age_seconds"] < 120)
        RECEIVE.validate(result)

    def test_fails_closed_if_factory_evidence_missing(self):
        self.state.unlink()
        with self.assertRaises(RuntimeError):
            SAMPLE.sample(home=self.home)

    def test_rejects_invalid_product_counts(self):
        data=json.loads(self.state.read_text())
        data["publishable_product_count"]=3
        self.state.write_text(json.dumps(data))
        with self.assertRaises(RuntimeError):
            SAMPLE.sample(home=self.home)


class FactoryReceiverTests(unittest.TestCase):
    def data(self):
        return {
            "schema_version":1, "source":"saeit_verified_ssh_vps_sampler",
            "observed_at":datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "loop_pid_verified":True, "activity_log_age_seconds":25,
            "product_cycle":{
                "built_product_count":2, "publishable_product_count":0,
                "artifact_qa_passed":True, "store_distribution_state":"not_connected",
                "age_seconds":65,
            },
        }

    def test_accepts_valid_bounded_sample(self):
        self.assertIsNotNone(RECEIVE.validate(self.data()))

    def test_rejects_fake_source_and_extra_payload_fields(self):
        data=self.data()
        data["source"]="unauthenticated"
        with self.assertRaises(ValueError):
            RECEIVE.validate(data)
        data=self.data()
        data["customer_data"]={"name":"must never be allowed"}
        with self.assertRaises(ValueError):
            RECEIVE.validate(data)

    def test_rejects_stale_time_and_malformed_types(self):
        data=self.data()
        data["observed_at"]=(datetime.datetime.now(datetime.timezone.utc)
                             - datetime.timedelta(hours=3)).isoformat()
        with self.assertRaises(ValueError):
            RECEIVE.validate(data)
        data=self.data()
        data["loop_pid_verified"]="yes"
        with self.assertRaises(ValueError):
            RECEIVE.validate(data)
        data=self.data()
        data["product_cycle"]["publishable_product_count"]=3
        with self.assertRaises(ValueError):
            RECEIVE.validate(data)


if __name__=="__main__":
    unittest.main()
