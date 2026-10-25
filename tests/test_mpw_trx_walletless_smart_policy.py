"""Walletless TRX decision engine: no real money, no DB and no RPC."""
import unittest
from datetime import datetime,timedelta,timezone
from unittest.mock import patch,Mock

from services.mpw_trx_walletless_core import PaymentHold,SolidifiedTransfer
from services.mpw_trx_walletless_smart_policy import (
    decide_candidate_next_step,advise_recheck,
)
from services.mpw_trx_walletless_reconcile import reconcile_queued_invoices

AT=datetime(2026,10,22,8,tzinfo=timezone.utc)
DEST="T"+"A"*33
SENDER="T"+"B"*33
TX="a"*64


def event(tx=TX,sun=1500000,minutes=1):
    return {"tx_hash":tx,"recipient":DEST,"amount_sun":sun,
            "block_time":AT+timedelta(minutes=minutes)}


def decision(items,used=None):
    return decide_candidate_next_step(recipient=DEST,amount_sun=1500000,
        issued_at=AT,expires_at=AT+timedelta(minutes=10),
        candidates=items,already_used=set() if used is None else used)


class IntelligentReconciliationTests(unittest.TestCase):
    def test_exact_amount_and_window_only_can_proceed_to_independent_proof(self):
        self.assertEqual(decision([event()]).code,"verify_dual_solidified_proof")
        self.assertEqual(decision([event()]).txid,TX)
        for item in (event(sun=1499999),event(sun=1500001),event(minutes=11)):
            with self.subTest(item=item):
                step=decision([item])
                self.assertEqual(step.code,"await_exact_transfer")
                self.assertIsNone(step.txid)
                self.assertFalse(step.requires_review)

    def test_ambiguous_or_replayed_payment_never_auto_settles(self):
        self.assertEqual(decision([event(),event(tx="b"*64)]).code,"ambiguous_transfer_hold")
        self.assertTrue(decision([event(),event(tx="b"*64)]).requires_review)
        self.assertEqual(decision([event()],{TX}).code,"reused_reference_hold")

    def test_untrusted_invoice_and_policy_stats_fail_closed(self):
        with self.assertRaises(PaymentHold):
            decide_candidate_next_step(recipient=DEST,amount_sun=True,issued_at=AT,
                expires_at=AT+timedelta(minutes=10),candidates=[],already_used=set())
        with self.assertRaises(PaymentHold):
            advise_recheck({"pending":1,"confirmed":True,"unmatched":0,"ambiguous":0,"held":0})

    def test_policy_recommends_only_safe_actions(self):
        base={"pending":1,"confirmed":0,"unmatched":0,"ambiguous":0,"held":0}
        for change,code in (({"unmatched":1},"continue_safe_chain_scan"),
                            ({"held":1},"retry_or_review_proof_hold"),
                            ({"ambiguous":1},"manual_ambiguity_review"),
                            ({"confirmed":1},"rescan_for_remaining_orders")):
            self.assertEqual(advise_recheck({**base,**change}).code,code)
        self.assertFalse(advise_recheck(base).requires_review)

    def test_integrated_loop_never_settles_ambiguous_payment(self):
        row=(71,"tron-mainnet",DEST,1500000,AT.replace(tzinfo=None),
             (AT+timedelta(minutes=10)).replace(tzinfo=None))
        never_settle=Mock()
        with (patch("services.mpw_trx_walletless_reconcile.candidates_for_auto_reconcile",return_value=[row]),
              patch("services.mpw_trx_walletless_reconcile.settle_isolated",never_settle)):
            stats=reconcile_queued_invoices(object(),
                lookup_tx_candidates=lambda:[event(),event(tx="b"*64)],
                independent_solidity_a=lambda tx:None,independent_solidity_b=lambda tx:None,
                sources_authenticated=True,legacy_tx_used=lambda *_:False,now=AT)
        never_settle.assert_not_called()
        self.assertEqual(stats["ambiguous"],1)
        self.assertTrue(stats["requires_review"])

    def test_integrated_loop_grants_only_after_two_proofs_and_atomic_settlement(self):
        row=(71,"tron-mainnet",DEST,1500000,AT.replace(tzinfo=None),
             (AT+timedelta(minutes=10)).replace(tzinfo=None))
        def proof(source):
            return SolidifiedTransfer(source,TX,"tron-mainnet",DEST,SENDER,1500000,
                                     AT+timedelta(minutes=1),True,True,True)
        with (patch("services.mpw_trx_walletless_reconcile.candidates_for_auto_reconcile",return_value=[row]),
              patch("services.mpw_trx_walletless_reconcile.settle_isolated",return_value="paid") as settle):
            stats=reconcile_queued_invoices(object(),lookup_tx_candidates=lambda:[event()],
                independent_solidity_a=lambda tx:proof("a"),
                independent_solidity_b=lambda tx:proof("b"),
                sources_authenticated=True,legacy_tx_used=lambda *_:False,now=AT)
        self.assertEqual(stats["confirmed"],1)
        self.assertEqual(settle.call_count,1)
        self.assertEqual(stats["safe_next_action"],"rescan_for_remaining_orders")


if __name__=="__main__":unittest.main()
