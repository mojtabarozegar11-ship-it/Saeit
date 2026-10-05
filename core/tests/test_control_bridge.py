import hashlib
import hmac
import json
import time
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from core.models import Agent, AgentCapability, AgentTask, AuditLog


class ControlBridgeTests(TestCase):
    def setUp(self):
        self.secret = "test-bridge-secret"
        self.agent = Agent.objects.create(
            code="factory-master-agent", name="Factory Master", mission="Build products", active=True
        )
        self.capability = AgentCapability.objects.create(
            code="product_research", name="Product research", risk_level="low", active=True
        )
        self.capability.agents.add(self.agent)

    def _signed(self, payload):
        raw = json.dumps(payload, separators=(",", ":")).encode()
        ts = str(int(time.time()))
        sig = hmac.new(self.secret.encode(), ts.encode() + b"." + raw, hashlib.sha256).hexdigest()
        return raw, {"HTTP_X_SAEIT_TIMESTAMP": ts, "HTTP_X_SAEIT_SIGNATURE": sig}

    def test_health_is_degraded_without_secret(self):
        with patch.dict("os.environ", {"SAEIT_BRIDGE_SECRET": ""}, clear=False):
            response = self.client.get("/api/bridge/health/")
        self.assertEqual(response.status_code, 503)

    def test_unsigned_dispatch_is_denied(self):
        with patch.dict("os.environ", {"SAEIT_BRIDGE_SECRET": self.secret}, clear=False):
            response = self.client.post(
                "/api/bridge/dispatch/", data=b'{"action":"product_research"}',
                content_type="application/json",
            )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(AgentTask.objects.count(), 0)

    def test_registered_low_risk_action_is_queued_and_audited(self):
        raw, headers = self._signed({"action": "product_research", "request": {"market": "global"}})
        with patch.dict("os.environ", {"SAEIT_BRIDGE_SECRET": self.secret}, clear=False):
            response = self.client.post(
                "/api/bridge/dispatch/", data=raw, content_type="application/json", **headers
            )
        self.assertEqual(response.status_code, 202)
        task = AgentTask.objects.get()
        self.assertEqual(task.status, "queued")
        self.assertEqual(task.agent, self.agent)
        self.assertEqual(task.input_data["market"], "global")
        self.assertTrue(AuditLog.objects.filter(action="bridge_task_created", target_id=str(task.pk)).exists())

    def test_unregistered_action_is_rejected(self):
        raw, headers = self._signed({"action": "arbitrary_shell", "request": {"command": "rm -rf /"}})
        with patch.dict("os.environ", {"SAEIT_BRIDGE_SECRET": self.secret}, clear=False):
            response = self.client.post(
                "/api/bridge/dispatch/", data=raw, content_type="application/json", **headers
            )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(AgentTask.objects.count(), 0)
