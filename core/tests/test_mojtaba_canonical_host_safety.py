"""Single canonical Django host composition; inert unless explicitly invoked."""
from django.test import TestCase

from ava_core.capabilities import ActionRequest, AdapterResult, CapabilitySpec, OperationSpec
from core.models import Agent, AuditLog, AgentTask
from core.mojtaba_host_runtime import build_canonical_runtime
from core.unified_bot_identity import BOT_CODE


class MojtabaCanonicalHostSafetyTests(TestCase):
    def setUp(self):
        self.canonical = Agent.objects.create(
            code=BOT_CODE, name="Mojtaba.bot.ai", mission="Only canonical identity",
            active=True,
        )

    def build(self, **overrides):
        args=dict(
            agent_id=self.canonical.pk, using="default",
            brain=lambda messages:"not invoked",
            propose_goals=lambda context:(),
            capabilities=(),
            authorize_action=lambda *_:False,
        )
        args.update(overrides)
        return build_canonical_runtime(**args)

    def test_canonical_host_build_has_zero_side_effects(self):
        before_agents=Agent.objects.count()
        before_tasks=AgentTask.objects.count()
        before_audit=AuditLog.objects.count()
        bot=self.build()
        self.assertEqual(bot.bot_name,"mojtaba.bot.ai")
        self.assertTrue(bot.status().durable_action_claim_store_configured)
        self.assertFalse(bot.status().brain_model_verified)
        self.assertFalse(bot.status().physical_actuation_enabled)
        self.assertEqual(bot.status().connected_capabilities,())
        self.assertEqual(Agent.objects.count(),before_agents)
        self.assertEqual(AgentTask.objects.count(),before_tasks)
        self.assertEqual(AuditLog.objects.count(),before_audit)

    def test_foreign_or_disabled_canonical_cannot_host_runtime(self):
        foreign=Agent.objects.create(
            code="legacy-review-only",name="Legacy role",
            mission="Do not merge or delete",active=True,
        )
        with self.assertRaises(PermissionError):
            self.build(agent_id=foreign.pk)
        self.canonical.active=False
        self.canonical.save(update_fields=["active"])
        with self.assertRaises(PermissionError):
            self.build()

    def test_no_implicit_authorization_or_database_alias(self):
        with self.assertRaises(TypeError):
            self.build(authorize_action=None)
        with self.assertRaises(ValueError):
            self.build(using="")
        with self.assertRaises(ValueError):
            self.build(using=None)

    def test_external_capability_needs_explicit_host_authorization(self):
        called=[]
        def adapter(request):
            called.append(request.request_id)
            return AdapterResult(True, "should never run without authorization")
        spec=CapabilitySpec("read_only_inspection",(OperationSpec("inspect","read"),))
        bot=self.build(capabilities=((spec,adapter),),authorize_action=lambda *_:False)
        req=ActionRequest("canonical-001",bot.owner_id,"read_only_inspection","inspect",{})
        with self.assertRaises(PermissionError):
            bot.execute_action(req)
        self.assertEqual(called,[])
        self.assertFalse(AuditLog.objects.filter(
            action="mojtaba_canonical_action_claim_v1",
        ).exists())
