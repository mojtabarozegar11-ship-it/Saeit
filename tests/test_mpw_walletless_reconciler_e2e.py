"""Auto reconcile synthetic scanner and two RPCs against isolated MariaDB."""
from datetime import datetime,timedelta,timezone
import unittest
from pathlib import Path
from services.mpw_trx_walletless_reconcile import reconcile_queued_invoices
from services.mpw_trx_walletless_reservation import reserve_isolated
from services.mpw_trx_walletless_finalize import paid_entitlement_isolated
from services.mpw_trx_walletless_core import SolidifiedTransfer
from tests.test_mpw_walletless_mariadb_reservation import connect,args,RECIPIENT,NOW

TX='c'*64
SENDER='T'+'B'*33

class AutomatedProofTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        c=connect()
        for statement in Path('services/sql/mpw_walletless_trx_isolated_v1.sql').read_text().split(';'):
            if statement.strip():
                with c.cursor() as cur:cur.execute(statement)
        c.commit();c.close()

    def setUp(self):
        self.c=connect()
        with self.c.cursor() as cur:
            for table in ('mpw_walletless_trx_entitlement_v1','mpw_walletless_trx_ledger_v1','mpw_walletless_trx_receipt_v1',
                  'mpw_walletless_trx_reservation_v1','mpw_walletless_trx_allocator_v1'):
                cur.execute('DELETE FROM '+table)
            cur.execute("INSERT INTO mpw_walletless_trx_allocator_v1 (recipient) VALUES (%s)",(RECIPIENT,))
        self.c.commit()
        self.id,self.sun,_=reserve_isolated(self.c,**args(order_id=31,customer_id=41))

    def tearDown(self):
        self.c.close()

    def event(self,tx=TX,amount=None):
        return {'tx_hash':tx,'recipient':RECIPIENT,'amount_sun':self.sun if amount is None else amount,
                'block_time':NOW+timedelta(minutes=1)}

    def proof(self,source,tx=TX,amount=None,valid=True):
        return SolidifiedTransfer(source_id=source,tx_hash=tx,network='tron-mainnet',
                  recipient=RECIPIENT,sender=SENDER,amount_sun=self.sun if amount is None else amount,
                  block_time=NOW+timedelta(minutes=1),solidified=valid,
                  transfer_contract=True,execution_success=True)

    def run_cycle(self,events=None,valid=True,second=None):
        return reconcile_queued_invoices(self.c,lookup_tx_candidates=lambda:[self.event()] if events is None else events,
             independent_solidity_a=lambda tx:self.proof('pinned-node-a',tx,valid=valid),
             independent_solidity_b=lambda tx:self.proof('pinned-node-b',tx if second is None else second),
             sources_authenticated=True,legacy_tx_used=lambda n,h:False,now=NOW)

    def test_detect_and_fulfill_without_customer_txid(self):
        state=self.run_cycle()
        self.assertEqual(state['confirmed'],1)
        self.assertTrue(paid_entitlement_isolated(self.c,invoice_id=self.id,customer_id=41))
        self.assertFalse(paid_entitlement_isolated(self.c,invoice_id=self.id,customer_id=12))
        self.assertEqual(self.run_cycle()['pending'],0)

    def test_inexact_amount_must_not_grant(self):
        state=self.run_cycle([self.event(amount=self.sun+1)])
        self.assertEqual(state['unmatched'],1)
        self.assertFalse(paid_entitlement_isolated(self.c,invoice_id=self.id,customer_id=41))

    def test_ambiguous_equal_amount_requires_manual_review(self):
        state=self.run_cycle([self.event(),self.event(tx='d'*64)])
        self.assertEqual(state['ambiguous'],1)
        self.assertFalse(paid_entitlement_isolated(self.c,invoice_id=self.id,customer_id=41))

    def test_one_provider_unfinalized_holds(self):
        state=self.run_cycle(valid=False)
        self.assertEqual(state['held'],1)
        self.assertFalse(paid_entitlement_isolated(self.c,invoice_id=self.id,customer_id=41))

    def test_providers_disagree_holds(self):
        state=self.run_cycle(second='d'*64)
        self.assertEqual(state['held'],1)
        self.assertFalse(paid_entitlement_isolated(self.c,invoice_id=self.id,customer_id=41))

    def test_scanned_hash_not_proof(self):
        state=self.run_cycle([{'tx_hash':TX,'recipient':RECIPIENT,'amount_sun':self.sun,
                              'block_time':NOW-timedelta(minutes=5)}])
        self.assertEqual(state['unmatched'],1)
        self.assertFalse(paid_entitlement_isolated(self.c,invoice_id=self.id,customer_id=41))

if __name__=='__main__':unittest.main()
