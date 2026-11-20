"""Database claim-store contract; no production effects."""
from django.db import connection, transaction
from django.test import TransactionTestCase, skipUnlessDBFeature

from ava_core.capabilities import ActionRequest, OperationSpec
from core.models import Agent, AuditLog
from core.mojtaba_action_claims import CLAIM_ACTION, DjangoCanonicalActionClaims


class CanonicalClaimsTests(TransactionTestCase):
    def setUp(self):
        agent = Agent.objects.create(code="mojtaba-bot-ai", name="Canonical", mission="test", active=True)
        self.owner = "agent-" + str(agent.pk)
        self.request = ActionRequest("private-reference", self.owner, "fixture", "submit", {"secret":"private-payload"})
        self.op = OperationSpec("submit", "write")

    def store(self):
        return DjangoCanonicalActionClaims(owner_id=self.owner, using="default")

    def test_backend_without_row_locks_denies(self):
        if connection.features.has_select_for_update:
            self.skipTest("Backend supports row locks")
        with self.assertRaises(RuntimeError):
            self.store().reserve(self.request, self.op)
        self.assertFalse(AuditLog.objects.filter(action=CLAIM_ACTION).exists())

    @skipUnlessDBFeature("has_select_for_update")
    def test_persistent_duplicate_and_redaction(self):
        self.assertTrue(self.store().reserve(self.request, self.op))
        self.assertFalse(self.store().reserve(self.request, self.op))
        row = AuditLog.objects.get(action=CLAIM_ACTION)
        self.assertNotIn("private", str(row.after_state))
        self.assertNotIn("private", row.trace_id)
        self.assertFalse(row.after_state["external_outcome_verified"])

    @skipUnlessDBFeature("has_select_for_update")
    def test_nested_transaction_refused(self):
        with transaction.atomic():
            with self.assertRaises(RuntimeError):
                self.store().reserve(self.request, self.op)
        self.assertFalse(AuditLog.objects.filter(action=CLAIM_ACTION).exists())
