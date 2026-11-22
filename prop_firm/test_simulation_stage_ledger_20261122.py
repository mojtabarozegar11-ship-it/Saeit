"""Focused isolated tests for the 14-level simulation transition ledger."""

from decimal import Decimal as D
from unittest.mock import patch

from django.test import TestCase

from prop_firm.models import (
    PropSimulationAccount,
    PropSimulationIdentity,
    PropSimulationInvoiceOwner,
    PropSimulationStageTransition,
)
from prop_firm.simulation_stage_ledger import (
    SimulationStageTransitionRejected,
    commit_next_simulated_level,
)
from prop_firm.rules import LEVELS


DB = "default"
PERFORMANCE = "a" * 64
CAPACITY = "b" * 64


class SimulationStageLedgerTests(TestCase):
    databases = {DB}

    def setUp(self):
        self.alias_patch = patch(
            "prop_firm.simulation_stage_ledger.MOJPROP_DB_ALIAS",
            DB,
        )
        self.alias_patch.start()
        self.addCleanup(self.alias_patch.stop)
        identity = PropSimulationIdentity.objects.using(DB).create(
            subject_key="stage-ledger-test",
            email_digest="c" * 64,
            status="active",
        )
        owner = PropSimulationInvoiceOwner.objects.using(DB).create(
            identity=identity,
            invoice_ref="stage-ledger-invoice",
            buyer_email_digest=identity.email_digest,
            settlement_reference="fixture-settlement",
            settlement_verified=True,
            contract_version="2026-11-21/simulation-v2",
        )
        self.account = PropSimulationAccount.objects.using(DB).create(
            identity=identity,
            invoice_owner=owner,
            account_ref="stage-ledger-account",
            kind=PropSimulationAccount.Kind.FUNDED_SIMULATION,
            status=PropSimulationAccount.Status.PASSED,
            tier_index=0,
            starting_capital_usd=D("1000.00"),
            policy_version="2026-11-21/simulation-v2",
        )

    def commit(self, key="transition-1"):
        return commit_next_simulated_level(
            account_ref=self.account.account_ref,
            transition_key=key,
            performance_evidence_digest=PERFORMANCE,
            capacity_evidence_digest=CAPACITY,
            verified_pass=True,
            capacity_verified=True,
        )

    def test_commits_exactly_one_level(self):
        result = self.commit()
        self.assertEqual(result["status"], "committed")
        self.assertEqual(result["from_tier"], 0)
        self.assertEqual(result["to_tier"], 1)
        account = PropSimulationAccount.objects.using(DB).get(pk=self.account.pk)
        self.assertEqual(account.tier_index, 1)
        self.assertEqual(account.starting_capital_usd, D(str(LEVELS[1])))
        self.assertEqual(account.status, PropSimulationAccount.Status.ACTIVE)
        self.assertEqual(
            PropSimulationStageTransition.objects.using(DB).filter(
                account=account
            ).count(),
            1,
        )

    def test_identical_retry_is_idempotent(self):
        first = self.commit()
        second = self.commit()
        self.assertEqual(second["status"], "idempotent_replay")
        self.assertEqual(second["transition_id"], first["transition_id"])
        self.assertEqual(
            PropSimulationStageTransition.objects.using(DB)
            .filter(account=self.account)
            .count(),
            1,
        )

    def test_conflicting_retry_is_rejected(self):
        self.commit()
        with self.assertRaises(SimulationStageTransitionRejected):
            commit_next_simulated_level(
                account_ref=self.account.account_ref,
                transition_key="transition-1",
                performance_evidence_digest="d" * 64,
                capacity_evidence_digest=CAPACITY,
                verified_pass=True,
                capacity_verified=True,
            )

    def test_unverified_pass_and_capacity_are_rejected(self):
        with self.assertRaises(SimulationStageTransitionRejected):
            commit_next_simulated_level(
                account_ref=self.account.account_ref,
                transition_key="transition-unverified",
                performance_evidence_digest=PERFORMANCE,
                capacity_evidence_digest=CAPACITY,
                verified_pass=False,
                capacity_verified=True,
            )
        with self.assertRaises(SimulationStageTransitionRejected):
            commit_next_simulated_level(
                account_ref=self.account.account_ref,
                transition_key="capacity-unverified",
                performance_evidence_digest=PERFORMANCE,
                capacity_evidence_digest=CAPACITY,
                verified_pass=True,
                capacity_verified=False,
            )
        self.assertEqual(
            PropSimulationStageTransition.objects.using(DB).filter(
                account=self.account
            ).count(),
            0,
        )

    def test_only_funded_simulation_can_promote(self):
        self.account.kind = PropSimulationAccount.Kind.CHALLENGE
        self.account.save(using=DB)
        with self.assertRaises(SimulationStageTransitionRejected):
            self.commit("challenge-cannot-promote")

    def test_settlement_is_required(self):
        self.account.invoice_owner.settlement_verified = False
        self.account.invoice_owner.settlement_reference = ""
        self.account.invoice_owner.save(using=DB)
        with self.assertRaises(SimulationStageTransitionRejected):
            self.commit("unsettled-cannot-promote")
