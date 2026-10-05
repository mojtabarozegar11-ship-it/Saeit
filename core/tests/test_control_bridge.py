import hashlib
import hmac
import json
import time
import uuid
from unittest.mock import patch

from django.test import TestCase

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
        nonce = uuid.uuid4().hex
        key = uuid.uuid4().hex
        signed = ts.encode() + b"." + nonce.encode() + b"." + key.encode() + b"." + raw
        sig = hmac.new(self.secret.encode(), signed, hashlib.sha256).hexdigest()
        return raw, {
            "HTTP_X_SAEIT_TIMESTAMP": ts,
            "HTTP_X_SAEIT_NONCE": nonce,
            "HTTP_X_SAEIT_IDEMPOTENCY_KEY": key,
            "HTTP_X_SAEIT_SIGNATURE": sig,
        }

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

    def test_replayed_signed_request_returns_existing_task(self):
        raw, headers = self._signed({"action": "product_research", "request": {"market": "global"}})
        with patch.dict("os.environ", {"SAEIT_BRIDGE_SECRET": self.secret}, clear=False):
            first = self.client.post("/api/bridge/dispatch/", data=raw, content_type="application/json", **headers)
            second = self.client.post("/api/bridge/dispatch/", data=raw, content_type="application/json", **headers)
        self.assertEqual(first.status_code, 202)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json()["status"], "duplicate")
        self.assertEqual(AgentTask.objects.count(), 1)
        self.assertTrue(AuditLog.objects.filter(action="bridge_idempotent_retry").exists())

    def test_idempotency_key_cannot_be_reused_for_different_body(self):
        raw, headers = self._signed({"action": "product_research", "request": {"market": "global"}})
        with patch.dict("os.environ", {"SAEIT_BRIDGE_SECRET": self.secret}, clear=False):
            first = self.client.post("/api/bridge/dispatch/", data=raw, content_type="application/json", **headers)
            changed, changed_headers = self._signed({"action": "product_research", "request": {"market": "other"}})
            changed_headers["HTTP_X_SAEIT_IDEMPOTENCY_KEY"] = headers["HTTP_X_SAEIT_IDEMPOTENCY_KEY"]
            ts = changed_headers["HTTP_X_SAEIT_TIMESTAMP"]
            nonce = changed_headers["HTTP_X_SAEIT_NONCE"]
            key = changed_headers["HTTP_X_SAEIT_IDEMPOTENCY_KEY"]
            signed = ts.encode() + b"." + nonce.encode() + b"." + key.encode() + b"." + changed
            changed_headers["HTTP_X_SAEIT_SIGNATURE"] = hmac.new(self.secret.encode(), signed, hashlib.sha256).hexdigest()
            second = self.client.post("/api/bridge/dispatch/", data=changed, content_type="application/json", **changed_headers)
        self.assertEqual(first.status_code, 202)
        self.assertEqual(second.status_code, 409)
        self.assertEqual(AgentTask.objects.count(), 1)

    def test_invalid_risk_is_audited_and_rejected_without_500(self):
        raw, headers = self._signed({"action": "product_research", "risk": "unknown", "request": {}})
        with patch.dict("os.environ", {"SAEIT_BRIDGE_SECRET": self.secret}, clear=False):
            response = self.client.post("/api/bridge/dispatch/", data=raw, content_type="application/json", **headers)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["reason"], "invalid_risk")
        self.assertEqual(AgentTask.objects.count(), 0)
        self.assertTrue(AuditLog.objects.filter(action="bridge_dispatch_rejected", after_state__reason="invalid_risk").exists())
