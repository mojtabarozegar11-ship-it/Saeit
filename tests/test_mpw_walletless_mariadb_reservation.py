"""MariaDB ephemeral test only; never touches MojPlayWin production DB."""
import os,threading,unittest
from pathlib import Path
from decimal import Decimal
from datetime import datetime, timedelta, timezone
import pymysql

from services.mpw_trx_walletless_core import PaymentHold
from services.mpw_trx_walletless_reservation import reserve_isolated

RECIPIENT='T'+'A'*33
NOW=datetime(2026,10,22,0,0,tzinfo=timezone.utc)

def connect():
    return pymysql.connect(host="127.0.0.1",port=3306,user="walletless",password="local-only-no-money",
                           database="walletless_ci",autocommit=False)

def args(order_id=11,customer_id=22,random_below=lambda n:0):
    return dict(order_id=order_id,customer_id=customer_id,recipient=RECIPIENT,
                usd_total=Decimal("0.03"),usd_per_trx=Decimal("0.30"),quote_observed_at=NOW,
                now=NOW,random_below=random_below,legacy_amount_reserved=lambda amount:False)

class EphemeralMariaDBTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        c=connect()
        sql=Path("services/sql/mpw_walletless_trx_isolated_v1.sql").read_text()
        for statement in sql.split(";"):
            if statement.strip():
                with c.cursor() as cur:cur.execute(statement)
        c.commit();c.close()

    def setUp(self):
        self.c=connect()
        with self.c.cursor() as cur:
            cur.execute("DELETE FROM mpw_walletless_trx_reservation_v1")
            cur.execute("DELETE FROM mpw_walletless_trx_allocator_v1")
            cur.execute("INSERT INTO mpw_walletless_trx_allocator_v1 (recipient) VALUES (%s)",(RECIPIENT,))
        self.c.commit()

    def tearDown(self):
        self.c.close()

    def test_persistent_reservation_and_idempotency(self):
        ix,amount,created=reserve_isolated(self.c,**args())
        self.assertTrue(created);self.assertEqual(amount,100000)
        repeat=reserve_isolated(self.c,**args())
        self.assertEqual(repeat,(ix,amount,False))
        with self.c.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM mpw_walletless_trx_reservation_v1")
            self.assertEqual(cur.fetchone()[0],1)

    def test_unique_amount_after_collision(self):
        reserve_isolated(self.c,**args())
        vals=iter([0,1])
        _,amount,created=reserve_isolated(self.c,**args(order_id=12,random_below=lambda hi:next(vals)))
        self.assertTrue(created);self.assertEqual(amount,100001)

    def test_legacy_collision_checker_enforced(self):
        kw=args()
        kw['legacy_amount_reserved']=lambda amt:True
        with self.assertRaises(PaymentHold):
            reserve_isolated(self.c,**kw)
        with self.c.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM mpw_walletless_trx_reservation_v1")
            self.assertEqual(cur.fetchone()[0],0)

    def test_unseeded_receiver_denied(self):
        with self.c.cursor() as cur:cur.execute("DELETE FROM mpw_walletless_trx_allocator_v1")
        self.c.commit()
        with self.assertRaises(PaymentHold):
            reserve_isolated(self.c,**args())

    def test_order_cannot_be_reassigned(self):
        reserve_isolated(self.c,**args())
        with self.assertRaises(PaymentHold):
            reserve_isolated(self.c,**args(customer_id=33))

    def test_concurrent_allocation_serializes(self):
        results=[];errors=[]
        def reserve(o):
            c=connect()
            seq=iter(range(32))
            try:results.append(reserve_isolated(c,**args(order_id=o,random_below=lambda hi:next(seq))))
            except Exception as exc:errors.append(type(exc).__name__)
            finally:c.close()
        a=threading.Thread(target=reserve,args=(200,))
        b=threading.Thread(target=reserve,args=(201,))
        a.start();b.start();a.join(timeout=20);b.join(timeout=20)
        self.assertFalse(a.is_alive() or b.is_alive())
        self.assertFalse(errors,errors)
        self.assertEqual({x[1] for x in results},{100000,100001})

if __name__=='__main__':unittest.main()
