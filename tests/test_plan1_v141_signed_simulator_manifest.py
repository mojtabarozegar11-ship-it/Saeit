"""Signed simulator ledger intake: no real broker, customer, funds or trading."""
import unittest
from dataclasses import asdict, is_dataclass, replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import hmac
import json

from prop_firm.plan1_v141_signed_simulator_manifest import (
    SCHEMA, SIGN_PREFIX, HmacLedgerReview, LedgerManifestRejected,
    verify_and_replay_signed_simulator_manifest,
)
from tests.test_plan1_v141_simulated_challenge_engine import good_snapshot, NOW

KEY=b"K"*32
SOURCE="allowlisted.simulator.adapter"
KEY_ID="review.adapter.v1"
MANIFEST_ID="LEDGER-ABCDEFGHIJKLMNOP"


def encode(v):
    if isinstance(v,datetime):
        return v.astimezone(timezone.utc).isoformat().replace("+00:00","Z")
    if is_dataclass(v):
        return {key:encode(value) for key,value in asdict(v).items()}
    if isinstance(v,dict):
        return {key:encode(value) for key,value in v.items()}
    if isinstance(v,(list,tuple)):
        return [encode(value) for value in v]
    return v


def payload():
    return dict(schema=SCHEMA,source=SOURCE,key_id=KEY_ID,
                manifest_id=MANIFEST_ID,sequence=1,issued_at=encode(NOW),
                snapshot=encode(good_snapshot()))


def build(doc=None):
    doc=payload() if doc is None else doc
    raw=json.dumps(doc,sort_keys=True,separators=(",",":"),
                   ensure_ascii=True,allow_nan=False).encode("utf-8")
    signature=hmac.new(KEY,SIGN_PREFIX+raw,"sha256").hexdigest()
    return raw,signature


def ingest(raw=None,signature=None,**kwargs):
    original,original_sign=build()
    return verify_and_replay_signed_simulator_manifest(
        raw_manifest=original if raw is None else raw,
        hmac_signature=original_sign if signature is None else signature,
        trusted_signer_keys=kwargs.pop("trusted_signer_keys",{KEY_ID:KEY}),
        expected_source=kwargs.pop("expected_source",SOURCE),
        expected_key_id=kwargs.pop("expected_key_id",KEY_ID),
        expected_manifest_id=kwargs.pop("expected_manifest_id",MANIFEST_ID),
        expected_challenge_ref=kwargs.pop(
            "expected_challenge_ref",good_snapshot().challenge_ref),
        expected_sequence=kwargs.pop("expected_sequence",1),
        now=kwargs.pop("now",NOW),**kwargs,
    )


class SignedManifestTests(unittest.TestCase):
    def test_01_valid_signed_50_trade_manifest_replays_both_phases(self):
        x=ingest()
        self.assertTrue(x.calculation.phase_math_complete)
        self.assertEqual(x.calculation.combined_unique_closed_positions,50)

    def test_02_adapter_hmac_not_broker_identity(self):
        x=ingest()
        self.assertTrue(x.configured_adapter_hmac_authenticated)
        self.assertFalse(x.regulated_broker_identity_proven)

    def test_03_no_paid_invoice_or_enrollment(self):
        x=ingest()
        self.assertFalse(x.checkout_authorized)
        self.assertFalse(x.paid_enrollment_authorized)

    def test_04_no_real_order_or_payout(self):
        x=ingest()
        self.assertFalse(x.real_orders_authorized)
        self.assertFalse(x.payout_authorized)

    def test_05_no_external_ledger_completeness_claim(self):
        x=ingest()
        self.assertFalse(x.independent_event_history_completeness_proven)
        self.assertFalse(x.trusted_persistent_replay_registry_implemented_here)

    def test_06_raw_manifest_digest_exact_sha256(self):
        raw,sig=build()
        self.assertEqual(ingest().raw_manifest_sha256,sha256(raw).hexdigest())

    def test_07_wrong_signature_rejected(self):
        with self.assertRaises(LedgerManifestRejected):
            ingest(signature="0"*64)

    def test_08_wrong_trusted_key_material_rejected(self):
        with self.assertRaises(LedgerManifestRejected):
            ingest(trusted_signer_keys={KEY_ID:b"L"*32})

    def test_09_short_key_rejected(self):
        with self.assertRaises(LedgerManifestRejected):
            ingest(trusted_signer_keys={KEY_ID:b"x"*10})

    def test_10_missing_key_rejected(self):
        with self.assertRaises(LedgerManifestRejected):
            ingest(trusted_signer_keys={})

    def test_11_wrong_expected_source_rejected(self):
        with self.assertRaises(LedgerManifestRejected):
            ingest(expected_source="another.feed")

    def test_12_wrong_expected_key_id_rejected(self):
        with self.assertRaises(LedgerManifestRejected):
            ingest(expected_key_id="another.key")

    def test_13_wrong_expected_sequence_rejected(self):
        with self.assertRaises(LedgerManifestRejected):
            ingest(expected_sequence=2)

    def test_14_replay_manifest_id_mismatch_rejected(self):
        with self.assertRaises(LedgerManifestRejected):
            ingest(expected_manifest_id="LEDGER-ZYXWVUTSRQPONMLK")

    def test_15_challenge_ref_mismatch_rejected(self):
        with self.assertRaises(LedgerManifestRejected):
            ingest(expected_challenge_ref="CHALLENGE-ZYXWVUTSRQPONMLK")

    def test_16_contract_digest_tamper_rejected_even_when_resigned(self):
        doc=payload()
        doc["snapshot"]["accepted_terms_sha256"]="a"*64
        raw,sig=build(doc)
        with self.assertRaises(LedgerManifestRejected):
            ingest(raw=raw,signature=sig)

    def test_17_manifest_source_tamper_rejected_even_when_resigned(self):
        doc=payload()
        doc["source"]="untrusted.feed"
        raw,sig=build(doc)
        with self.assertRaises(LedgerManifestRejected):
            ingest(raw=raw,signature=sig)

    def test_18_manifest_stale_11_minutes_rejected(self):
        doc=payload()
        doc["issued_at"]=encode(NOW-timedelta(minutes=11))
        raw,sig=build(doc)
        with self.assertRaises(LedgerManifestRejected):
            ingest(raw=raw,signature=sig)

    def test_19_manifest_from_future_rejected(self):
        doc=payload()
        doc["issued_at"]=encode(NOW+timedelta(minutes=1))
        raw,sig=build(doc)
        with self.assertRaises(LedgerManifestRejected):
            ingest(raw=raw,signature=sig)

    def test_20_noncanonical_utc_time_rejected(self):
        doc=payload()
        doc["issued_at"]=NOW.isoformat()
        raw,sig=build(doc)
        with self.assertRaises(LedgerManifestRejected):
            ingest(raw=raw,signature=sig)

    def test_21_naive_trusted_clock_rejected(self):
        with self.assertRaises(LedgerManifestRejected):
            ingest(now=NOW.replace(tzinfo=None))

    def test_22_duplicate_signed_json_key_rejected(self):
        raw,_=build()
        bad=b'{"schema":"evil",'+raw[1:]
        sign=hmac.new(KEY,SIGN_PREFIX+bad,"sha256").hexdigest()
        with self.assertRaises(LedgerManifestRejected):
            ingest(raw=bad,signature=sign)

    def test_23_synthetic_float_money_rejected(self):
        doc=payload()
        doc["snapshot"]["closed_fills"][0]["gross_realized_usd"]=0.4
        raw,sig=build(doc)
        with self.assertRaises(LedgerManifestRejected):
            ingest(raw=raw,signature=sig)

    def test_24_extra_unrecognized_event_field_rejected(self):
        doc=payload()
        doc["snapshot"]["closed_fills"][0]["extra_is_authorized"]=True
        raw,sig=build(doc)
        with self.assertRaises(LedgerManifestRejected):
            ingest(raw=raw,signature=sig)

    def test_25_missing_phase_equity_field_rejected(self):
        doc=payload()
        del doc["snapshot"]["equity_marks"][0]["is_utc_day_open"]
        raw,sig=build(doc)
        with self.assertRaises(LedgerManifestRejected):
            ingest(raw=raw,signature=sig)

    def test_26_absurd_trusted_sequence_type_rejected(self):
        with self.assertRaises(LedgerManifestRejected):
            ingest(expected_sequence=True)

    def test_27_manifest_assessment_after_issued_rejected(self):
        doc=payload()
        doc["snapshot"]["as_of"]=encode(NOW+timedelta(seconds=1))
        raw,sig=build(doc)
        with self.assertRaises(LedgerManifestRejected):
            ingest(raw=raw,signature=sig)

    def test_28_unverified_trade_remains_blocked_despite_valid_hmac(self):
        doc=payload()
        doc["snapshot"]["closed_fills"][0]["reconciliation_status"]="pending"
        raw,sig=build(doc)
        self.assertIn("unreconciled_close_event",
                      ingest(raw=raw,signature=sig).calculation.blockers)

    def test_29_unsafe_list_more_than_five_thousand_events_rejected(self):
        doc=payload()
        doc["snapshot"]["equity_marks"]=doc["snapshot"]["equity_marks"]*180
        raw,sig=build(doc)
        with self.assertRaises(LedgerManifestRejected):
            ingest(raw=raw,signature=sig)

    def test_30_integrity_error_after_valid_signature_not_checkout(self):
        doc=payload()
        doc["snapshot"]["closed_fills"][0]["symbol"]="EURUSD"
        raw,sig=build(doc)
        x=ingest(raw=raw,signature=sig)
        self.assertFalse(x.calculation.phase_math_complete)
        self.assertFalse(x.checkout_authorized)


    def test_31_fresh_signature_does_not_refresh_stale_simulator_snapshot(self):
        doc=payload()
        doc["snapshot"]["as_of"]=encode(NOW-timedelta(minutes=11))
        raw,sig=build(doc)
        with self.assertRaises(LedgerManifestRejected):
            ingest(raw=raw,signature=sig)

    def test_32_exact_ten_minute_simulator_age_boundary_allowed(self):
        doc=payload()
        doc["snapshot"]["as_of"]=encode(NOW-timedelta(minutes=10))
        raw,sig=build(doc)
        x=ingest(raw=raw,signature=sig)
        self.assertEqual(x.sequence,1)
        self.assertEqual(x.calculation.combined_unique_closed_positions,50)

    def test_33_one_second_over_ten_minute_simulator_age_rejected(self):
        doc=payload()
        doc["snapshot"]["as_of"]=encode(NOW-timedelta(minutes=10,seconds=1))
        raw,sig=build(doc)
        with self.assertRaises(LedgerManifestRejected):
            ingest(raw=raw,signature=sig)


if __name__=="__main__":
    unittest.main()
