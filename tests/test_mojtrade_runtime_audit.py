"""Regression checks for the VPS-only, read-only MojTrade health evidence."""

import contextlib
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "deploy" / "audit_agent_fleet_vps_readonly.sh"


class MojTradeRuntimeAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        script = AUDIT.read_text(encoding="utf-8")
        blocks = re.findall(r"<<'PY'\n(.*?)\nPY", script, re.DOTALL)
        cls.audit_block = compile(blocks[-1], str(AUDIT), "exec")

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.ops = self.home / "factory-runtime/operations/mojtrade"
        self.private = self.home / "factory-runtime/private/mojtrade"
        self.ops.mkdir(parents=True)
        self.private.mkdir(parents=True)
        os.chmod(self.private, 0o700)

    def prepare_private_evidence(self, expires_minutes=90):
        source = b"# retained observer source\n"
        observer = self.ops / "observer.py"
        observer.write_bytes(source)
        os.chmod(observer, 0o600)
        receipt = {
            "source_sha256": hashlib.sha256(source).hexdigest(),
            "execution": "disabled", "orders": 0,
            "publication_enabled": False,
        }
        now = datetime.now(timezone.utc)
        payload = {
            "schema_version": 1, "source": "mojtrade-vps",
            "generated_at": (now - timedelta(minutes=2)).isoformat(),
            "expires_at": (now + timedelta(minutes=expires_minutes)).isoformat(),
            "signals": [{"symbol": "BTC/USD"}, {"symbol": "ETH/USD"}],
        }
        for filename, data in (("activation-receipt.json", receipt),
                               ("validated-payload.json", payload)):
            target = self.private / filename
            target.write_text(json.dumps(data), encoding="utf-8")
            os.chmod(target, 0o600)

    def run_audit(self, scheduled):
        cron_line = (
            "13 * * * * /usr/bin/flock -n /private/observer.lock "
            "/private/observer.py --output /private/payload.json "
            "# SAEIT_MOJTRADE_OBSERVER_V1\n"
        ) if scheduled else ""

        def fake_run(command, **kwargs):
            if command[:2] == ["crontab", "-l"]:
                return subprocess.CompletedProcess(command, 0, stdout=cron_line)
            if command[:2] == ["ps", "-eo"]:
                return subprocess.CompletedProcess(command, 0, stdout="")
            raise AssertionError(f"Unexpected external call: {command}")

        output = io.StringIO()
        with patch("pathlib.Path.home", return_value=self.home), \
             patch("subprocess.run", side_effect=fake_run), \
             contextlib.redirect_stdout(output):
            exec(self.audit_block, {"__name__": "__main__"})
        marker = "AGENT_FLEET_MOJTRADE_RUNTIME="
        return json.loads(next(line[len(marker):] for line in output.getvalue().splitlines()
                               if line.startswith(marker)))

    def test_fresh_private_receipt_and_hourly_schedule(self):
        self.prepare_private_evidence()
        result = self.run_audit(scheduled=True)
        self.assertTrue(result["observer_operational_evidence"])
        self.assertEqual(result["cron_entries"], 1)
        self.assertFalse(result["real_trading_supported_by_observer"])

    def test_source_files_without_activation_do_not_count_as_live(self):
        self.prepare_private_evidence()
        result = self.run_audit(scheduled=False)
        self.assertFalse(result["observer_operational_evidence"])

    def test_missing_or_expired_payload_cannot_certify_operation(self):
        self.assertFalse(self.run_audit(scheduled=True)["payload_fresh"])
        self.prepare_private_evidence(expires_minutes=-1)
        result = self.run_audit(scheduled=True)
        self.assertFalse(result["payload_fresh"])
        self.assertFalse(result["observer_operational_evidence"])


if __name__ == "__main__":
    unittest.main()
