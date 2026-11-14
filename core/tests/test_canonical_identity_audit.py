from django.test import TestCase

from core.canonical_bot_identity import audit_identity_rows
from core.models import Agent


class CanonicalIdentityAuditTests(TestCase):
    def setUp(self):
        Agent.objects.all().delete()

    def test_audit_reports_parallel_identities_without_mutation(self):
        Agent.objects.create(
            code="economic-master-agent",
            name="Legacy economic",
            mission="legacy",
            active=True,
        )
        Agent.objects.create(
            code="content-director",
            name="Legacy content",
            mission="legacy",
            active=True,
        )
        report = audit_identity_rows(Agent)
        self.assertEqual(report["status"], "parallel_identities_blocked")
        self.assertEqual(report["active_count"], 2)
        self.assertFalse(report["retirement_authorized"])
        self.assertEqual(Agent.objects.filter(active=True).count(), 2)

    def test_audit_accepts_canonical_only(self):
        Agent.objects.create(
            code="mojtaba-bot-ai",
            name="Mojtaba.bot.ai",
            mission="canonical",
            active=True,
        )
        report = audit_identity_rows(Agent)
        self.assertEqual(report["status"], "canonical_only")
        self.assertEqual(report["active_codes"], ["mojtaba-bot-ai"])


    def test_factory_and_content_roles_are_not_second_master_runtimes(self):
        Agent.objects.create(
            code="mojtaba-bot-ai", name="Single", mission="master", active=True,
        )
        Agent.objects.create(
            code="moj_1ro_1", name="Factory adapter", mission="factory", active=True,
        )
        Agent.objects.create(
            code="content-director", name="Content adapter", mission="content", active=True,
        )
        report = audit_identity_rows(Agent)
        self.assertEqual(report["status"], "parallel_identities_blocked")
        self.assertEqual(report["runtime_status"], "canonical_runtime_active")
        self.assertEqual(report["runtime_active_codes"], ["mojtaba-bot-ai"])
        self.assertEqual(report["runtime_active_count"], 1)

    def test_parallel_master_runtimes_remain_explicitly_blocked(self):
        Agent.objects.create(
            code="economic-master-agent", name="Old", mission="legacy", active=True,
        )
        Agent.objects.create(
            code="mojtaba-bot-ai", name="New", mission="canonical", active=True,
        )
        report = audit_identity_rows(Agent)
        self.assertEqual(report["runtime_status"],
                         "multiple_active_runtime_identities_blocked")
        self.assertEqual(report["runtime_active_count"], 2)
        self.assertFalse(report["retirement_authorized"])

    def test_only_legacy_master_is_not_reported_as_canonical(self):
        Agent.objects.create(
            code="economic-master-agent", name="Old", mission="legacy", active=True,
        )
        report = audit_identity_rows(Agent)
        self.assertEqual(report["runtime_status"], "legacy_runtime_active")
        self.assertEqual(report["runtime_active_codes"], ["economic-master-agent"])

    def test_no_active_master_is_separate_from_other_active_agents(self):
        Agent.objects.create(
            code="moj_1ro_1", name="Factory", mission="factory", active=True,
        )
        report = audit_identity_rows(Agent)
        self.assertEqual(report["runtime_status"], "no_active_master_runtime")
        self.assertEqual(report["runtime_active_count"], 0)
