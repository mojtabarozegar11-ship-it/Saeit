from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase

from core.canonical_bot_identity import (
    CANONICAL_BOT_CODE,
    CANONICAL_BOT_ID,
    resolve_single_active_agent,
)
from core.models import Agent


class CanonicalBotIdentityTests(TestCase):
    def test_canonical_identity_is_fixed(self):
        self.assertEqual(CANONICAL_BOT_ID, "mojtaba.bot.ai")
        self.assertEqual(CANONICAL_BOT_CODE, "mojtaba-bot-ai")

    def test_legacy_alias_can_continue_only_as_the_single_runtime_row(self):
        legacy = Agent.objects.create(
            code="economic-master-agent",
            name="Legacy runtime alias",
            mission="handoff",
            active=True,
        )
        self.assertEqual(resolve_single_active_agent(Agent).pk, legacy.pk)

    def test_two_active_runtime_rows_fail_closed(self):
        Agent.objects.create(
            code="economic-master-agent",
            name="Legacy runtime alias",
            mission="handoff",
            active=True,
        )
        Agent.objects.create(
            code="mojtaba-bot-ai",
            name="Mojtaba.bot.ai",
            mission="canonical runtime",
            active=True,
        )
        with self.assertRaisesRegex(
            ImproperlyConfigured, "CANONICAL_BOT_MULTIPLE_ACTIVE"
        ):
            resolve_single_active_agent(Agent)
