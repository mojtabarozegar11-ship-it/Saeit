"""Canonical host composition, no provider or network calls."""
from django.test import TestCase
from unittest.mock import patch

from ava_core.capabilities import ActionRequest, AdapterResult, CapabilitySpec, OperationSpec
from core.models import Agent, AuditLog
from core.mojtaba_host_runtime import build_canonical_runtime
from core.mojtaba_site_dispatch import execute_site_cycle, SiteCycleClaims
from core.mojtaba_site_receipts import CLAIM, ACTION


class HostRuntimeTests(TestCase):
    def setUp(self):
        self.agent = Agent.objects.create(code="mojtaba-bot-ai",name="Canonical",mission="host",active=True)

    def build(self, **overrides):
        args = dict(agent_id=self.agent.pk, using="default",
            brain=lambda _: "not called", propose_goals=lambda _: (),
            capabilities=(), authorize_action=lambda *_: False)
        args.update(overrides)
        return build_canonical_runtime(**args)

    def test_composition_is_inert_and_attaches_default_claim_store(self):
        bot = self.build()
        self.assertEqual(bot.bot_name, "mojtaba.bot.ai")
        self.assertTrue(bot.status().durable_action_claim_store_configured)
        self.assertFalse(AuditLog.objects.exists())

    def test_inactive_or_foreign_agent_cannot_construct_runtime(self):
        other = Agent.objects.create(code="other",name="Other",mission="other",active=True)
        with self.assertRaises(PermissionError):
            self.build(agent_id=other.pk)
        self.agent.active=False
        self.agent.save(update_fields=["active"])
        with self.assertRaises(PermissionError):
            self.build()

    def test_authorization_rechecks_current_identity(self):
        adapter = lambda _: AdapterResult(True,"fixture")
        spec = CapabilitySpec("fixture",(OperationSpec("inspect","read"),))
        bot=self.build(capabilities=((spec,adapter),),authorize_action=lambda *_: True)
        self.agent.active=False
        self.agent.save(update_fields=["active"])
        with self.assertRaises(PermissionError):
            bot.execute_action(ActionRequest("one",bot.owner_id,"fixture","inspect",{}))
        self.assertFalse(AuditLog.objects.exists())

    def test_site_cycle_uses_common_runtime_and_claim_protocol(self):
        with patch("core.mojtaba_site_dispatch.build_canonical_runtime", wraps=build_canonical_runtime) as build:
            out=execute_site_cycle("a"*32,transport=lambda _: (200,"text/html",b"<html>"+b"x"*100+b"</html>"))
        build.assert_called_once()
        self.assertIsInstance(build.call_args.kwargs["claim_store"],SiteCycleClaims)
        self.assertEqual(out["site_receipts"],2)
        self.assertEqual(AuditLog.objects.filter(action=CLAIM).count(),1)
        self.assertEqual(AuditLog.objects.filter(action=ACTION).count(),2)

    def test_site_claim_store_rejects_mutating_effects(self):
        store=SiteCycleClaims(self.agent.pk,"a"*32)
        request=ActionRequest("a"*32,"agent-"+str(self.agent.pk),"site_observability","observe_public",{})
        with self.assertRaises(PermissionError):
            store.reserve(request,OperationSpec("observe_public","write"))
        self.assertFalse(AuditLog.objects.exists())
