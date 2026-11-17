"""No-order signed XAUUSD broker evidence acceptance and rejection tests."""
import hashlib
import hmac
import json
import unittest
from datetime import datetime, timedelta, timezone

from prop_firm.xauusd_v13_broker_evidence import (
    SCHEMA, SUBJECT, GoldEvidenceRejected, review_attested_xauusd_snapshot,
)
from prop_firm.xauusd_v13_preflight import DRAFT_CONTRACT_VERSION

NOW = datetime(2026, 11, 17, 12, tzinfo=timezone.utc)
SRC = "reviewed.trading.adapter"
ACCOUNT = "opaque.plan1.1"
KEY_ID = "independent.review.adapter"
KEY = "DUMMY-TEST-ONLY-DO-NOT-USE-IN-PRODUCTION-12345"


def sample(**changes):
    p=dict(schema=SCHEMA,product="MOJ-PROP-01",contract_version=DRAFT_CONTRACT_VERSION,
           source=SRC,account_ref=ACCOUNT,quote_ref="quote.001",
           quote_at="2026-11-17T12:00:00Z",reported_open_position_count=0,
           reported_open_risk_usd="0",open_positions=[],symbol="XAUUSD",
           account_currency="USD",initial_capital="100",equity="100",
           day_open_equity="100",side="buy",mid_price_per_oz="4000",
           stop_price_per_oz="3998.10",lot_quantity="0.01",minimum_lot="0.01",
           lot_step="0.01",ounces_per_lot="100",min_stop_distance_per_oz="0.2",
           full_spread_per_oz="0.3",slippage_reserve_per_oz="0.2",
           roundtrip_fees_usd="0.1",margin_required_usd="25",free_margin_usd="75")
    p.update(changes)
    return p


def serialize(doc):
    return json.dumps(doc,sort_keys=True,separators=(",",":"),allow_nan=False).encode()


def signature(raw, **changes):
    p=dict(attestation_id="attestation.1",kind="broker",subject_id=SUBJECT,
           source=SRC,key_id=KEY_ID,issued_at="2026-11-17T12:00:00Z",
           expires_at="2026-11-17T12:04:00Z",
           evidence_digest=hashlib.sha256(raw).hexdigest())
    p.update(changes)
    body=json.dumps(p,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()
    p["signature"]=hmac.new(KEY.encode(),b"MOJPROP-ATTESTATION-v1\n"+body,hashlib.sha256).hexdigest()
    return p


def review(doc=None,*,raw=None,packet=None,keys=None,now=NOW,expected_account=ACCOUNT,
           expected_source=SRC):
    raw=serialize(sample() if doc is None else doc) if raw is None else raw
    packet=signature(raw) if packet is None else packet
    return review_attested_xauusd_snapshot(
        raw_broker_snapshot=raw,attestation_packet=packet,
        trusted_attestation_keys={KEY_ID:KEY} if keys is None else keys,
        expected_source=expected_source,expected_account_ref=expected_account,now=now)


class GoldBindingTests(unittest.TestCase):
    def blocked(self,doc=None,**kwargs):
        with self.assertRaises(GoldEvidenceRejected):
            review(doc,**kwargs)

    def test_signed_nominal_math_only(self):
        r=review()
        self.assertTrue(r.result.mathematically_admissible)
        self.assertFalse(r.live_order_authorized)
        self.assertFalse(r.customer_invoice_authorized)
        self.assertFalse(r.broker_counterparty_independently_verified_by_this_module)

    def test_one_open_position(self):
        d=sample(open_positions=[dict(position_ref="pos.1",symbol="XAUUSD",risk_to_stop_usd="1")],
                 reported_open_position_count=1,reported_open_risk_usd="1")
        self.assertEqual(review(d).positions_reconciled_in_signed_packet,1)

    def test_intraday_floor_blocks_four_dollars(self):
        d=sample(open_positions=[dict(position_ref="pos.1",symbol="XAUUSD",risk_to_stop_usd="1.5")],
                 reported_open_position_count=1,reported_open_risk_usd="1.5")
        self.assertIn("projected_stops_breach_drawdown_limit",review(d).result.reasons)

    def test_eight_dollars_requires_intraday_profit(self):
        p=[dict(position_ref="pos.1",symbol="XAUUSD",risk_to_stop_usd="5.5")]
        d=sample(open_positions=p,reported_open_position_count=1,
                 reported_open_risk_usd="5.5",equity="109",day_open_equity="100")
        self.assertTrue(review(d).result.mathematically_admissible)
        d["day_open_equity"]="109"
        self.assertFalse(review(d).result.mathematically_admissible)

    def test_position_count_mismatch(self):
        self.blocked(sample(reported_open_position_count=1))

    def test_bool_position_count(self):
        self.blocked(sample(reported_open_position_count=True))

    def test_position_risk_mismatch(self):
        self.blocked(sample(reported_open_risk_usd="1"))

    def test_duplicate_positions(self):
        x=dict(position_ref="p.1",symbol="XAUUSD",risk_to_stop_usd="1")
        self.blocked(sample(open_positions=[x,x],reported_open_position_count=2,
                            reported_open_risk_usd="2"))

    def test_other_open_symbol(self):
        self.blocked(sample(open_positions=[dict(position_ref="p.1",symbol="BTCUSD",risk_to_stop_usd="1")],
                            reported_open_position_count=1,reported_open_risk_usd="1"))

    def test_negative_open_risk(self):
        self.blocked(sample(open_positions=[dict(position_ref="p.1",symbol="XAUUSD",risk_to_stop_usd="-1")],
                            reported_open_position_count=1,reported_open_risk_usd="-1"))

    def test_wrong_account(self):
        self.blocked(expected_account="different")

    def test_wrong_source(self):
        self.blocked(sample(source="fake-source"))

    def test_broker_attestation_wrong_kind(self):
        raw=serialize(sample())
        self.blocked(raw=raw,packet=signature(raw,kind="capital"))

    def test_broker_attestation_wrong_subject(self):
        raw=serialize(sample())
        self.blocked(raw=raw,packet=signature(raw,subject_id="moj-prop:OTHER:broker"))

    def test_invalid_digest(self):
        raw=serialize(sample())
        self.blocked(raw=raw,packet=signature(raw,evidence_digest="f"*64))

    def test_invalid_hmac(self):
        raw=serialize(sample())
        packet=signature(raw);packet["signature"]="a"*64
        self.blocked(raw=raw,packet=packet)

    def test_missing_key(self):
        self.blocked(keys={})

    def test_tampered_bytes(self):
        raw=serialize(sample());packet=signature(raw)
        self.blocked(raw=raw.replace(b"3998.10",b"3998.09"),packet=packet)

    def test_duplicate_json_key(self):
        raw=serialize(sample()).replace(b'"quote_ref":"quote.001"',
                                     b'"quote_ref":"quote.001","quote_ref":"quote.001"')
        self.blocked(raw=raw)

    def test_oversized_packet(self):
        self.blocked(raw=b"x"*16385)

    def test_wrong_contract(self):
        self.blocked(sample(contract_version="2026-11-15/v1.2"))

    def test_educational_sku(self):
        self.blocked(sample(product="MOJPROP-STARTER30"))

    def test_wrong_symbol(self):
        self.blocked(sample(symbol="EURUSD"))

    def test_wrong_currency(self):
        self.blocked(sample(account_currency="EUR"))

    def test_extra_sensitive_field_denied(self):
        self.blocked(sample(password="secret"))

    def test_no_float_accepted(self):
        self.blocked(sample(lot_quantity=0.01))

    def test_pathological_decimal_rejected(self):
        self.blocked(sample(lot_step="1e999999"))

    def test_stale_quote_math_denied(self):
        d=sample(quote_at="2026-11-17T11:54:00Z")
        self.assertIn("stale_or_future_quote",review(d).result.reasons)

    def test_expired_attestation(self):
        self.blocked(now=NOW+timedelta(minutes=6))

    def test_unverified_margin_denied(self):
        self.assertIn("insufficient_verified_free_margin",
                      review(sample(free_margin_usd="1")).result.reasons)

    def test_non_utc_time_rejected(self):
        self.blocked(sample(quote_at="2026-11-17T12:00:00+01:00"))

if __name__=="__main__":
    unittest.main()
