from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from prop_firm.models import (
    PropSimulationAccount,
    PropSimulationEvent,
    PropSimulationIdentity,
    PropSimulationInvoiceOwner,
)


class SimulationIsolationModelTests(TestCase):
    def setUp(self):
        self.identity = PropSimulationIdentity.objects.create(
            provider="email",
            subject_key="buyer-opaque-001",
            email_digest="a" * 64,
            status=PropSimulationIdentity.Status.ACTIVE,
        )
        self.owner = PropSimulationInvoiceOwner.objects.create(
            identity=self.identity,
            invoice_ref="MOJ-INV-001",
            buyer_email_digest="a" * 64,
            contract_version="moj-prop-v1",
            settlement_verified=True,
            settlement_reference="TRX-SETTLED-001",
        )

    def test_identity_has_no_auth_user_foreign_key(self):
        field_names = {field.name for field in PropSimulationIdentity._meta.fields}
        self.assertNotIn("user", field_names)

    def test_owner_rejects_identity_digest_mismatch(self):
        owner = PropSimulationInvoiceOwner(
            identity=self.identity,
            invoice_ref="MOJ-INV-002",
            buyer_email_digest="b" * 64,
            contract_version="moj-prop-v1",
        )
        with self.assertRaises(ValidationError):
            owner.full_clean()

    def test_account_rejects_unsettled_owner(self):
        pending = PropSimulationInvoiceOwner.objects.create(
            identity=self.identity,
            invoice_ref="MOJ-INV-PENDING",
            buyer_email_digest="a" * 64,
            contract_version="moj-prop-v1",
        )
        account = PropSimulationAccount(
            identity=self.identity,
            invoice_owner=pending,
            account_ref="SIM-001",
            kind=PropSimulationAccount.Kind.CHALLENGE,
            starting_capital_usd=Decimal("1000.00"),
        )
        with self.assertRaises(ValidationError):
            account.full_clean()

    def test_event_identity_is_idempotent_per_account(self):
        account = PropSimulationAccount.objects.create(
            identity=self.identity,
            invoice_owner=self.owner,
            account_ref="SIM-002",
            kind=PropSimulationAccount.Kind.CHALLENGE,
            starting_capital_usd=Decimal("1000.00"),
        )
        event_data = dict(
            account=account,
            event_ref="EVENT-001",
            sequence_no=1,
            event_type=PropSimulationEvent.EventType.STATUS,
            source="private-reconciler",
            occurred_at=timezone.now(),
            payload_digest="c" * 64,
            payload={"status": "active"},
        )
        PropSimulationEvent.objects.create(**event_data)
        with self.assertRaises(Exception):
            PropSimulationEvent.objects.create(**event_data)

    def test_login_code_is_not_a_persisted_plaintext_field(self):
        field_names = {field.name for field in PropSimulationIdentity._meta.fields}
        self.assertNotIn("login_code", field_names)
