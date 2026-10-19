"""MojPlayWin V91 agent admin charts: real private state, never fabricated data."""
import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace

from django.http import Http404
from django.test import RequestFactory, SimpleTestCase, override_settings
from django.urls import resolve, reverse

from command_center import mpw_v91_agent_metrics as metrics
from command_center.mpw_v91_agent_views import private_mpw_agent_metrics

class AgentPerformanceUnitTests(SimpleTestCase):
    def test_unknown_when_private_record_unavailable(self):
        with patch.object(metrics,"PRIVATE_STATE",Path("/nonexistent-mpw-private-agents-state-20261018")):
            snap=metrics.snapshot(now=datetime(2026,10,18,6,tzinfo=timezone.utc))
        self.assertEqual(snap["state"],"unavailable")
        self.assertEqual(snap["agents"],[])
        self.assertFalse(snap["historical_failures_measured"])

    def test_verified_draft_count_is_per_agent_and_last_14_days(self):
        now=datetime(2026,10,18,6,tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as tmp:
            state=Path(tmp)
            for folder in ("queue","processed","drafts"):
                (state/folder).mkdir(mode=0o700)
            (state/"heartbeat.json").write_text(json.dumps({
                "status":"active_private","tenant":"mojplaywin-main","master_generation":64,
                "auto_publish":False,"factory_connected":False,
                "last_master_callback_utc":"2026-10-18T05:40:00Z",
            }),encoding="utf8")
            def done(kind,name,date):
                request={"tenant":"mojplaywin-main","review_only":True,"kind":kind,"title":name}
                raw=json.dumps(request,ensure_ascii=False).encode("utf8")
                (state/"processed"/(name+".json")).write_bytes(raw)
                token=hashlib.sha256(raw).hexdigest()[:24]
                (state/"drafts"/(token+".json")).write_text(json.dumps({
                    "generated_utc":date,
                    "draft":{"tenant":"mojplaywin-main","review_required":True,"published":False}
                }),encoding="utf8")
            done("research_digest","research-1","2026-10-18T04:00:00Z")
            done("research_digest","old-research","2026-08-17T04:00:00Z")
            done("product_blueprint","product-1","2026-10-17T04:00:00Z")
            (state/"queue"/"pending.json").write_text(json.dumps({
                "tenant":"mojplaywin-main","review_only":True,"kind":"research_digest"
            }),encoding="utf8")
            (state/"queue"/"outside-tenant.json").write_text(json.dumps({
                "tenant":"zomorodmelal","review_only":True,"kind":"product_blueprint"
            }),encoding="utf8")
            with patch.object(metrics,"PRIVATE_STATE",state):
                snap=metrics.snapshot(now=now)
        self.assertEqual(snap["state"],"active_private")
        agents={a["id"]:a for a in snap["agents"]}
        self.assertEqual(set(agents),{"master_gen64","research_digest","product_blueprint"})
        self.assertEqual(agents["research_digest"]["completed"],1)
        self.assertEqual(agents["research_digest"]["queue"],1)
        self.assertEqual(agents["research_digest"]["series"][-1],1)
        self.assertEqual(agents["product_blueprint"]["completed"],1)
        self.assertEqual(agents["product_blueprint"]["queue"],0)
        self.assertEqual(agents["product_blueprint"]["series"][-2],1)
        self.assertEqual(len(agents["research_digest"]["days"]),14)
        self.assertIsNone(agents["master_gen64"]["series"])
        self.assertFalse(agents["master_gen64"]["history_available"])
        self.assertFalse(snap["historical_failures_measured"])
        self.assertFalse(snap["auto_publish"])

    def test_stale_heartbeat_is_not_misrepresented_as_online(self):
        now=datetime(2026,10,18,6,tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/"heartbeat.json").write_text(json.dumps({
                "tenant":"mojplaywin-main","master_generation":64,
                "auto_publish":False,"factory_connected":False,
                "last_master_callback_utc":"2026-10-17T01:00:00Z",
            }),encoding="utf8")
            with patch.object(metrics,"PRIVATE_STATE",root):
                result=metrics.snapshot(now=now)
        self.assertEqual(result["state"],"stale_heartbeat")
        self.assertEqual(result["agents"][0]["status"],"stale_heartbeat")

class AgentAdminHostIsolationTests(SimpleTestCase):
    def setUp(self):
        self.factory=RequestFactory()
        self.staff=SimpleNamespace(is_staff=True,is_active=True,is_authenticated=True)
        self.other=SimpleNamespace(is_staff=False,is_active=True,is_authenticated=True)

    def test_main_host_staff_can_see_status_but_other_domains_cannot(self):
        with override_settings(ALLOWED_HOSTS=["mojplaywin.com","zomorodmelal.ir"]):
            req=self.factory.get("/staff/command-center/api/mojplaywin/v91/performance/",
                                 HTTP_HOST="zomorodmelal.ir")
            req.user=self.staff
            with self.assertRaises(Http404):
                private_mpw_agent_metrics(req)
            req=self.factory.get("/staff/command-center/api/mojplaywin/v91/performance/",
                                 HTTP_HOST="mojplaywin.com")
            req.user=self.other
            response=private_mpw_agent_metrics(req)
            self.assertEqual(response.status_code,302)
            req.user=self.staff
            with patch.object(metrics,"PRIVATE_STATE",Path("/nonexistent-mpw-private-agents-state-20261018")):
                response=private_mpw_agent_metrics(req)
            self.assertEqual(response.status_code,200)
            self.assertEqual(response["Cache-Control"],"private, no-store, max-age=0")
            self.assertIn("noindex",response["X-Robots-Tag"])

    def test_private_only_routes_and_template_host_guard(self):
        self.assertEqual(reverse("mpw_private_v91_agent_performance"),
            "/staff/command-center/api/mojplaywin/v91/performance/")
        self.assertEqual(reverse("mojplaywin_v91_review"),
            "/staff/command-center/api/mojplaywin/v91/review/")
        from django.urls import Resolver404
        with self.assertRaises(Resolver404):
            resolve("/agents/v91/review/")
        dashboard=Path(__file__).resolve().parents[1]/"command_center"/"templates"/"command_center"/"dashboard.html"
        text=dashboard.read_text(encoding="utf8")
        self.assertIn("{% if mpw_main_host %}",text)
        self.assertIn("mpw_v91_agent_performance.html",text)
        template=dashboard.parent/"mpw_v91_agent_performance.html"
        source=template.read_text(encoding="utf8")
        self.assertIn("agent.setting",source)
        self.assertIn("drawChart(card,agent)",source)
        self.assertIn("history_available",source)
