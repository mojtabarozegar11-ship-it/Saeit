from django.test import TestCase

from core.canonical_bot_identity import audit_identity_rows
from core.models import Agent


class CanonicalIdentityAuditTests(TestCase):
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
