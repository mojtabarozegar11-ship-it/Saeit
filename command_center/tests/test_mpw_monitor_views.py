from unittest.mock import patch
from core.models import Agent
from core.mojtaba_site_receipts import record_public_cycle
from core.mojtaba_site_fleet import CANONICAL_BOT, ROUTES
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse


@override_settings(ALLOWED_HOSTS=["mojplaywin.com", "zomorodmelal.ir", "testserver"])
class PrivateMpwMonitorTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="mpw-monitor-staff", password="test-pass", is_staff=True)
        self.viewer = get_user_model().objects.create_user(
            username="mpw-monitor-viewer", password="test-pass")
        self.path = reverse("mpw_agent_monitor")
        self.api = reverse("mpw_agent_monitor_api")

    def test_staff_only_view_and_api(self):
        self.client.force_login(self.user)
        with patch("command_center.mpw_monitor_views.snapshot", return_value={
            "tenant": "mojplaywin-main", "items": [], "summary": {}, "source": "private_cpanel_unavailable"
        }):
            response = self.client.get(self.api, HTTP_HOST="mojplaywin.com")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["items"], [])
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(response["X-Robots-Tag"], "noindex, nofollow")
        self.assertEqual(self.client.get(self.path, HTTP_HOST="mojplaywin.com").status_code, 200)

    def test_staff_can_compare_canonical_public_receipts_without_other_tenant_data(self):
        Agent.objects.create(code="mojtaba-bot-ai", name="Canonical", mission="read only", active=True)
        rows = []
        for tenant, roles in ROUTES.items():
            for role in roles:
                rows.append({"bot": CANONICAL_BOT, "tenant": tenant, "role": role,
                             "state": "http_probe_ok", "http_status": 200,
                             "response_sha256": "a"*64})
        record_public_cycle({"canonical_bot": CANONICAL_BOT,
                             "public_checks_count": 14,
                             "observations": rows}, cycle_id="a"*32)
        self.client.force_login(self.user)
        with patch("command_center.mpw_monitor_views.snapshot", return_value={
            "tenant": "mojplaywin-main", "items": [], "summary": {},
            "source": "private_cpanel_unavailable",
        }):
            data = self.client.get(self.api, HTTP_HOST="mojplaywin.com").json()
        self.assertEqual(data["canonical_public_monitor"]["canonical_bot"], CANONICAL_BOT)
        self.assertEqual(data["canonical_public_monitor"]["successful_public_observation_receipts_24h"], 1)
        self.assertFalse(data["canonical_public_monitor"]["legacy_collector_retirement_authorized"])
        self.assertNotIn("zomorodmelal", str(data))
        self.assertEqual(data["tenant"], "mojplaywin-main")

    def test_failing_auditlog_does_not_break_existing_private_monitor(self):
        from django.db import DatabaseError
        self.client.force_login(self.user)
        with patch("command_center.mpw_monitor_views.snapshot", return_value={
            "tenant": "mojplaywin-main", "items": [], "summary": {},
            "source": "private_cpanel_unavailable",
        }), patch("command_center.mpw_monitor_views.inspect_public_monitor_continuity",
                  side_effect=DatabaseError("audit offline")):
            data = self.client.get(self.api, HTTP_HOST="mojplaywin.com").json()
        self.assertEqual(data["canonical_public_monitor"]["state"], "auditlog_unavailable")
        self.assertFalse(data["canonical_public_monitor"]["private_worker_replaced"])

    def test_other_domains_are_denied(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(self.api, HTTP_HOST="zomorodmelal.ir").status_code, 404)
        self.assertEqual(self.client.get(self.path, HTTP_HOST="zomorodmelal.ir").status_code, 404)

    def test_nonstaff_must_not_receive_private_data(self):
        self.client.force_login(self.viewer)
        self.assertNotEqual(self.client.get(self.api, HTTP_HOST="mojplaywin.com").status_code, 200)
        self.client.logout()
        self.assertNotEqual(self.client.get(self.api, HTTP_HOST="mojplaywin.com").status_code, 200)

    def test_no_write_methods(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.post(self.api, HTTP_HOST="mojplaywin.com").status_code, 405)
