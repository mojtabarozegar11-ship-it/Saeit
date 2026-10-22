"""Isolated real MariaDB settlement simulations; no live invoices or money."""
import unittest
from pathlib import Path
from dataclasses import replace
from datetime import datetime,timedelta,timezone
from decimal import Decimal
import pymysql
from services.mpw_trx_walletless_core import PaymentHold,SolidifiedTransfer
from services.mpw_trx_walletless_reservation import reserve_isolated
from services.mpw_trx_walletless_finalize import settle_isolated,paid_entitlement_isolated,candidates_for_auto_reconcile
from tests.test_mpw_walletless_mariadb_reservation import connect,args,RECIPIENT,NOW

SENDER='T'+'B'*33
TX1='a'*64
TX2='b'*64

def solid(source,amount,tx=TX1,**kwargs):
    v=dict(source_id=source,tx_hash=tx,network='tron-mainnet',
      recipient=RECIPIENT,sender=SENDER,amount_sun=amount,
      block_time=NOW+timedelta(seconds=75),solidified=True,
      transfer_contract=True,execution_success=True)
    v.update(kwargs)
    return SolidifiedTransfer(**v)

class AtomicPaymentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        c=connect()
        for sql in Path('services/sql/mpw_walletless_trx_isolated_v1.sql').read_text().split(';'):
            if sql.strip():
                with c.cursor() as cur:cur.execute(sql)
        c.commit();c.close()

    def setUp(self):
        self.c=connect()
        with self.c.cursor() as cur:
            for table in ('mpw_walletless_trx_entitlement_v1','mpw_walletless_trx_ledger_v1','mpw_walletless_trx_receipt_v1',
                          'mpw_walletless_trx_reservation_v1','mpw_walletless_trx_allocator_v1'):
                cur.execute('DELETE FROM '+table)
            cur.execute("INSERT INTO mpw_walletless_trx_allocator_v1 (recipient) VALUES (%s)",(RECIPIENT,))
        self.c.commit()

    def first(self,o=21,c=42):
        id_,amt,_=reserve_isolated(self.c,**args(order_id=o,customer_id=c,random_below=lambda hi:o-21))
        return id_,amt

    def settle(self,invoice,amount,tx=TX1,**kwargs):
        return settle_isolated(self.c,invoice,solid('rpc-one',amount,tx,**kwargs),
               solid('rpc-two',amount,tx,**kwargs),legacy_tx_used=lambda net,h:False,
               sources_authenticated=True)

    def test_full_chain_invoice_receipt_ledger_download(self):
        invoice,amount=self.first()
        self.assertFalse(paid_entitlement_isolated(self.c,invoice_id=invoice,customer_id=42))
        self.assertEqual(self.settle(invoice,amount),'paid')
        self.assertTrue(paid_entitlement_isolated(self.c,invoice_id=invoice,customer_id=42))
        self.assertFalse(paid_entitlement_isolated(self.c,invoice_id=invoice,customer_id=43))
        self.assertFalse(paid_entitlement_isolated(self.c,invoice_id=invoice+7,customer_id=42))

    def test_replay_denied_with_atomic_rollback(self):
        invoice,amount=self.first()
        self.settle(invoice,amount)
        with self.assertRaises(PaymentHold):
            self.settle(invoice,amount)
        with self.c.cursor() as cur:
            for table in ('mpw_walletless_trx_receipt_v1','mpw_walletless_trx_ledger_v1','mpw_walletless_trx_entitlement_v1'):
                cur.execute('SELECT COUNT(*) FROM '+table)
                self.assertEqual(cur.fetchone()[0],1)

    def test_wrong_amount_does_not_write_any_record(self):
        invoice,amount=self.first()
        with self.assertRaises(PaymentHold):
            self.settle(invoice,amount+1)
        self.assertFalse(paid_entitlement_isolated(self.c,invoice_id=invoice,customer_id=42))
        with self.c.cursor() as cur:
            for table in ('mpw_walletless_trx_receipt_v1','mpw_walletless_trx_ledger_v1','mpw_walletless_trx_entitlement_v1'):
                cur.execute('SELECT COUNT(*) FROM '+table)
                self.assertEqual(cur.fetchone()[0],0)

    def test_unverified_sources_blocked(self):
        invoice,amount=self.first()
        with self.assertRaises(PaymentHold):
            settle_isolated(self.c,invoice,solid('rpc-a',amount),solid('rpc-b',amount),
                legacy_tx_used=lambda a,b:False,sources_authenticated=False)
        self.assertFalse(paid_entitlement_isolated(self.c,invoice_id=invoice,customer_id=42))

    def test_spent_in_existing_gateway_denied(self):
        invoice,amount=self.first()
        with self.assertRaises(PaymentHold):
            settle_isolated(self.c,invoice,solid('rpc-a',amount),solid('rpc-b',amount),
                legacy_tx_used=lambda a,b:True,sources_authenticated=True)
        self.assertFalse(paid_entitlement_isolated(self.c,invoice_id=invoice,customer_id=42))

    def test_duplicate_hash_between_orders_denied(self):
        ix1,amount1=self.first()
        ix2,amount2=self.first(o=22,c=43)
        self.settle(ix1,amount1)
        with self.assertRaises(PaymentHold):
            self.settle(ix2,amount2)
        self.assertFalse(paid_entitlement_isolated(self.c,invoice_id=ix2,customer_id=43))

    def test_reconciler_queue_bounded_and_private(self):
        invoice,amount=self.first()
        work=candidates_for_auto_reconcile(self.c,max_items=1)
        self.assertEqual(len(work),1)
        self.assertEqual(work[0][0],invoice)
        self.settle(invoice,amount)
        self.assertEqual(candidates_for_auto_reconcile(self.c),[])

    def test_inconsistent_financial_record_denies_file(self):
        invoice,amount=self.first()
        self.settle(invoice,amount)
        with self.c.cursor() as cur:
            cur.execute("UPDATE mpw_walletless_trx_ledger_v1 SET amount_usd='0.04' WHERE invoice_id=%s",(invoice,))
        self.c.commit()
        self.assertFalse(paid_entitlement_isolated(self.c,invoice_id=invoice,customer_id=42))

    def test_no_real_proof_when_timestamp_outside(self):
        invoice,amount=self.first()
        with self.assertRaises(PaymentHold):
            self.settle(invoice,amount,block_time=NOW+timedelta(hours=1))
        self.assertFalse(paid_entitlement_isolated(self.c,invoice_id=invoice,customer_id=42))

if __name__=='__main__': unittest.main()
