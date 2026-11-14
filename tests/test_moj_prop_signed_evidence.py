"""No-network signed evidence ingestion tests. No funding, trading or payment actions."""
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from prop_firm.models import PropAccount, PropTrader, PropExecution, PropEquityObservation
from prop_firm.signed_evidence import EvidenceRejected, ingest_signed_evidence

KEY = "private-ci-only-signature-key-1234567890-not-live"
SOURCE = "broker_contract_ci"
NOW = datetime(2026, 11, 14, 18, 0, tzinfo=timezone.utc)
ISSUED = "2026-11-14T18:00:00Z"
RECORDED = "2026-11-14T17:59:00Z"


@override_settings(MOJ_PROP_TRUSTED_EVIDENCE_KEYS={SOURCE: KEY})
class BrokerSignedEvidenceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="signed_evidence_ci", password="unrelated-test-only-password"
        )
        cls.profile = PropTrader.objects.create(user=cls.user)
        cls.account = PropAccount.objects.create(
            trader=cls.profile, kind=PropAccount.Kind.PHASE_ONE,
        )

    def packet(self, *, account_id=None, event_id="external-1",
               event_type="execution", data=None, source=SOURCE,
               recorded_at=RECORDED, issued_at=ISSUED,
               key=KEY, corrupt_sig=False):
        account_id = account_id or self.account.id
        if data is None:
            data = {"symbol": "EURUSD", "gross_usd": "5.50", "fees_usd": "0.50"}
        obj = {
            "account_id": str(account_id), "event_id": event_id,
            "event_type": event_type, "recorded_at": recorded_at, "data": data,
        }
        raw = json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode()
        msg = b"MOJPROP-EVIDENCE-v1\n" + source.encode() + b"\n" + str(account_id).encode() + b"\n" + issued_at.encode() + b"\n" + raw
        sig = hmac.new(key.encode(), msg, hashlib.sha256).hexdigest()
        if corrupt_sig:
            sig = ("0" if sig[0] != "0" else "1") + sig[1:]
        return dict(
            account_id=account_id, source=source, raw=raw, signature=sig,
            issued_at=issued_at, now=NOW,
        )

    def test_valid_execution_is_pending_not_verified(self):
        result = ingest_signed_evidence(**self.packet())
        self.assertEqual(result["result"], "recorded_pending")
        self.assertFalse(result["verified"])
        row = PropExecution.objects.get(account=self.account, external_event_id="external-1")
        self.assertEqual(row.reconciliation_status, "pending")
        self.assertEqual(row.net_realized_usd, Decimal("5.0000"))
        self.assertEqual(row.evidence_digest, result["digest"])

    def test_duplicate_identical_event_idempotent(self):
        payload = self.packet()
        ingest_signed_evidence(**payload)
        output = ingest_signed_evidence(**payload)
        self.assertEqual(output["result"], "already_recorded")
        self.assertEqual(PropExecution.objects.filter(account=self.account).count(), 1)

    def test_conflicting_event_id_fails(self):
        ingest_signed_evidence(**self.packet())
        with self.assertRaises(EvidenceRejected):
            ingest_signed_evidence(**self.packet(data={
                "symbol": "EURUSD", "gross_usd": "1000", "fees_usd": "0"
            }))

    def test_bad_signature_fails_before_db(self):
        with self.assertRaises(EvidenceRejected):
            ingest_signed_evidence(**self.packet(corrupt_sig=True))
        self.assertFalse(PropExecution.objects.exists())

    def test_unknown_source_fails(self):
        with self.assertRaises(EvidenceRejected):
            ingest_signed_evidence(**self.packet(source="evil-source"))

    def test_wrong_source_key_fails(self):
        with self.assertRaises(EvidenceRejected):
            ingest_signed_evidence(**self.packet(key="different-secret-that-is-long-enough"))

    def test_replayed_old_time_fails(self):
        with self.assertRaises(EvidenceRejected):
            ingest_signed_evidence(**self.packet(issued_at="2026-11-14T17:40:00Z"))

    def test_far_future_signature_fails(self):
        with self.assertRaises(EvidenceRejected):
            ingest_signed_evidence(**self.packet(issued_at="2026-11-14T18:20:00Z"))

    def test_wrong_account_identity_fails(self):
        wrong = self.packet(account_id=UUID("00000000-0000-0000-0000-000000000009"))
        with self.assertRaises(EvidenceRejected):
            ingest_signed_evidence(**wrong)
        self.assertFalse(PropExecution.objects.exists())

    def test_signed_position_identity_and_bot_origin_are_stored_pending(self):
        payload=self.packet(data={
            "symbol":"XAUUSD", "gross_usd":"2.50", "fees_usd":"0.50",
            "position_id":"broker-position-1001", "execution_origin":"bot",
        })
        result=ingest_signed_evidence(**payload)
        self.assertEqual(result["result"],"recorded_pending")
        row=PropExecution.objects.get(account=self.account)
        self.assertEqual(row.external_position_id,"broker-position-1001")
        self.assertEqual(row.execution_origin,"bot")
        self.assertEqual(row.reconciliation_status,"pending")

    def test_legacy_execution_without_position_id_does_not_fake_a_trade(self):
        ingest_signed_evidence(**self.packet())
        row=PropExecution.objects.get(account=self.account)
        self.assertEqual(row.external_position_id,"")
        self.assertEqual(row.execution_origin,"unknown")
        # Even a later independent reconciliation cannot invent a distinct
        # closed position from legacy execution packets lacking a position ID.
        row.reconciliation_status="verified"
        row.save(update_fields=["reconciliation_status"])
        from prop_firm.trade_count import count_challenge_trades
        stats=count_challenge_trades([row],paid_at=NOW-timedelta(days=1))
        self.assertEqual(stats.valid_closed_positions,0)

    def test_partial_signed_execution_metadata_is_rejected(self):
        for payload in (
            {"symbol":"XAUUSD","gross_usd":"1","fees_usd":"0","position_id":"id1"},
            {"symbol":"XAUUSD","gross_usd":"1","fees_usd":"0","execution_origin":"bot"},
        ):
            with self.subTest(payload=payload), self.assertRaises(EvidenceRejected):
                ingest_signed_evidence(**self.packet(data=payload))

    def test_unsupported_bot_origin_is_rejected_even_if_signed(self):
        payload={"symbol":"XAUUSD","gross_usd":"1","fees_usd":"0",
                 "position_id":"pos7","execution_origin":"spoofed"}
        with self.assertRaises(EvidenceRejected):
            ingest_signed_evidence(**self.packet(data=payload))

    def test_valid_equity_mark_is_pending(self):
        result = ingest_signed_evidence(**self.packet(
            event_type="equity", event_id="mark-1",
            data={"equity_usd": "100.0000", "is_session_open": True},
        ))
        row = PropEquityObservation.objects.get(account=self.account)
        self.assertEqual(result["result"], "recorded_pending")
        self.assertEqual(row.reconciliation_status, "pending")
        self.assertTrue(row.is_session_open)

    def test_missing_equity_flag_rejected(self):
        with self.assertRaises(EvidenceRejected):
            ingest_signed_evidence(**self.packet(
                event_type="equity", data={"equity_usd": "99"},
            ))

    def test_non_boolean_open_session_rejected(self):
        with self.assertRaises(EvidenceRejected):
            ingest_signed_evidence(**self.packet(
                event_type="equity", data={"equity_usd": "100", "is_session_open": 1},
            ))

    def test_negative_equity_rejected(self):
        with self.assertRaises(EvidenceRejected):
            ingest_signed_evidence(**self.packet(
                event_type="equity", data={"equity_usd": "-1", "is_session_open": False},
            ))

    def test_negative_fees_rejected(self):
        with self.assertRaises(EvidenceRejected):
            ingest_signed_evidence(**self.packet(
                data={"symbol": "BTCUSD", "gross_usd": "10", "fees_usd": "-1"},
            ))

    def test_nan_and_float_input_rejected(self):
        for gross in ("NaN", "Infinity", 5.3):
            with self.subTest(gross=gross), self.assertRaises(EvidenceRejected):
                ingest_signed_evidence(**self.packet(
                    data={"symbol": "BTCUSD", "gross_usd": gross, "fees_usd": "0"},
                ))

    def test_unknown_event_type_rejected(self):
        with self.assertRaises(EvidenceRejected):
            ingest_signed_evidence(**self.packet(event_type="withdrawal"))

    def test_extra_execution_fields_rejected(self):
        with self.assertRaises(EvidenceRejected):
            ingest_signed_evidence(**self.packet(data={
                "symbol": "EURUSD", "gross_usd": "10", "fees_usd": "0",
                "payout_address": "malicious",
            }))

    def test_future_event_time_rejected(self):
        with self.assertRaises(EvidenceRejected):
            ingest_signed_evidence(**self.packet(recorded_at="2026-11-15T18:00:00Z"))

    def test_closed_account_rejected(self):
        self.account.status = PropAccount.Status.CLOSED
        self.account.save()
        with self.assertRaises(EvidenceRejected):
            ingest_signed_evidence(**self.packet())

    def test_breached_account_rejected(self):
        self.account.status = PropAccount.Status.BREACHED
        self.account.save()
        with self.assertRaises(EvidenceRejected):
            ingest_signed_evidence(**self.packet())

    def test_oversized_body_rejected(self):
        kwargs = self.packet()
        kwargs["raw"] = b"x" * 20000
        with self.assertRaises(EvidenceRejected):
            ingest_signed_evidence(**kwargs)

    def test_invalid_identifier_rejected(self):
        with self.assertRaises(EvidenceRejected):
            ingest_signed_evidence(**self.packet(event_id="../../bad"))

    def test_no_secret_configuration_rejected(self):
        with override_settings(MOJ_PROP_TRUSTED_EVIDENCE_KEYS={}):
            with self.assertRaises(EvidenceRejected):
                ingest_signed_evidence(**self.packet())

    def test_evidence_without_reconciliation_never_qualifies(self):
        from prop_firm.portal import account_projection
        ingest_signed_evidence(**self.packet())
        projection = account_projection(self.account)
        self.assertFalse(projection["verified"])
        self.assertEqual(projection["net_profit"], 0)
        self.assertIsNone(projection["assessment"])

    def test_cross_type_replay_of_upstream_event_id_is_rejected(self):
        ingest_signed_evidence(**self.packet(event_id="same-event"))
        with self.assertRaisesRegex(EvidenceRejected, "reused across event types"):
            ingest_signed_evidence(**self.packet(
                event_type="equity", event_id="same-event",
                data={"equity_usd": "100", "is_session_open": False},
            ))
        self.assertEqual(PropExecution.objects.count(), 1)
        self.assertEqual(PropEquityObservation.objects.count(), 0)

    def test_reverse_cross_type_replay_is_rejected(self):
        ingest_signed_evidence(**self.packet(
            event_type="equity", event_id="same-event",
            data={"equity_usd": "100", "is_session_open": False},
        ))
        with self.assertRaisesRegex(EvidenceRejected, "reused across event types"):
            ingest_signed_evidence(**self.packet(event_id="same-event"))
        self.assertEqual(PropExecution.objects.count(), 0)
        self.assertEqual(PropEquityObservation.objects.count(), 1)

    def test_trailing_zeros_up_to_four_places_accepted(self):
        for amount in ("100", "100.0", "100.0000", "0.0000", "1E+2"):
            with self.subTest(amount=amount):
                packet = self.packet(
                    event_type="equity", event_id="mark" + str(len(amount)) + amount.replace(".","_").replace("+","_"),
                    data={"equity_usd": amount, "is_session_open": False},
                )
                result = ingest_signed_evidence(**packet)
                self.assertEqual(result["result"], "recorded_pending")

    def test_reject_more_than_four_effective_fractional_digits(self):
        with self.assertRaises(EvidenceRejected):
            ingest_signed_evidence(**self.packet(
                event_type="equity", event_id="too-precise",
                data={"equity_usd": "100.00001", "is_session_open": False},
            ))

    def test_reject_more_than_fourteen_integer_digits(self):
        with self.assertRaises(EvidenceRejected):
            ingest_signed_evidence(**self.packet(
                event_type="equity", event_id="too-large",
                data={"equity_usd": "100000000000000", "is_session_open": False},
            ))

    def test_upper_ledger_boundary_accepted(self):
        result = ingest_signed_evidence(**self.packet(
            event_type="equity", event_id="valid-boundary",
            data={"equity_usd": "99999999999999.9999", "is_session_open": False},
        ))
        self.assertEqual(result["result"], "recorded_pending")

    def _signed_raw(self, raw):
        packet = self.packet()
        packet["raw"] = raw
        msg = (b"MOJPROP-EVIDENCE-v1\n" + SOURCE.encode() + b"\n"
               + str(self.account.id).encode() + b"\n" + ISSUED.encode()
               + b"\n" + raw)
        packet["signature"] = hmac.new(KEY.encode(), msg, hashlib.sha256).hexdigest()
        return packet

    def test_signed_duplicate_top_level_key_rejected(self):
        raw = ('{"account_id":"%s","event_id":"event-a","event_id":"event-b",'
               '"event_type":"execution","recorded_at":"%s",'
               '"data":{"symbol":"EURUSD","gross_usd":"5","fees_usd":"0"}}'
               % (self.account.id, RECORDED)).encode()
        with self.assertRaisesRegex(EvidenceRejected, "Duplicate JSON"):
            ingest_signed_evidence(**self._signed_raw(raw))
        self.assertFalse(PropExecution.objects.exists())

    def test_signed_duplicate_nested_financial_key_rejected(self):
        raw = ('{"account_id":"%s","event_id":"event-a",'
               '"event_type":"execution","recorded_at":"%s",'
               '"data":{"symbol":"EURUSD","gross_usd":"5",'
               '"gross_usd":"5000","fees_usd":"0"}}'
               % (self.account.id, RECORDED)).encode()
        with self.assertRaisesRegex(EvidenceRejected, "Duplicate JSON"):
            ingest_signed_evidence(**self._signed_raw(raw))
        self.assertFalse(PropExecution.objects.exists())

    def test_signed_nonfinite_json_literal_rejected(self):
        raw = ('{"account_id":"%s","event_id":"event-a",'
               '"event_type":"execution","recorded_at":"%s",'
               '"data":{"symbol":"EURUSD","gross_usd":NaN,"fees_usd":"0"}}'
               % (self.account.id, RECORDED)).encode()
        with self.assertRaisesRegex(EvidenceRejected, "Non-finite JSON"):
            ingest_signed_evidence(**self._signed_raw(raw))
        self.assertFalse(PropExecution.objects.exists())

    def test_signed_excessively_nested_json_fails_closed(self):
        # Valid HMAC, invalid parser depth: no uncaught RecursionError or DB row.
        raw = (b"[" * 1200) + b"0" + (b"]" * 1200)
        with self.assertRaisesRegex(EvidenceRejected, "JSON nesting limit exceeded|Invalid UTF-8 JSON evidence"):
            ingest_signed_evidence(**self._signed_raw(raw))
        self.assertFalse(PropExecution.objects.exists())
        self.assertFalse(PropEquityObservation.objects.exists())
