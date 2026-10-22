"""Preproduction atomic walletless TRX simulation, NOT production ledger/grant."""
from datetime import timezone
from decimal import Decimal
import hashlib
import json
from services.mpw_trx_walletless_core import InvoiceIntent, PaymentHold, verify_two_source_transfer

def settle_isolated(conn, invoice_id, proof_a, proof_b, *, legacy_tx_used, sources_authenticated):
    """Only TEST MariaDB. Provider proofs must come from independently authenticated server nodes."""
    if type(invoice_id) is not int or invoice_id <= 0 or sources_authenticated is not True or not callable(legacy_tx_used):
        raise PaymentHold("Untrusted invoice or independent provider")
    conn.begin()
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT id,order_id,customer_id,network,recipient,amount_sun,
                          total_usd,rate_usd_per_trx,issued_at,expires_at,status,verified_tx_hash
                          FROM mpw_walletless_trx_reservation_v1 WHERE id=%s FOR UPDATE""",(invoice_id,))
            row=cur.fetchone()
            if row is None:
                raise PaymentHold("Unknown invoice")
            (id_,order_id,customer_id,network,recipient,amount_sun,total_usd,
             rate,issued_at,expires_at,status,paid_tx)=row
            if status!="awaiting" or paid_tx is not None:
                raise PaymentHold("Already settled or expired")
            invoice=InvoiceIntent(order_id=int(order_id),customer_id=int(customer_id),
                network=network,recipient=recipient,amount_sun=int(amount_sun),
                usd_total=Decimal(str(total_usd)),quote_usd_per_trx=Decimal(str(rate)),
                issued_at=issued_at.replace(tzinfo=timezone.utc),
                expires_at=expires_at.replace(tzinfo=timezone.utc))
            def already_used(net,tx):
                cur.execute("SELECT invoice_id FROM mpw_walletless_trx_receipt_v1 WHERE network=%s AND tx_hash=%s",(net,tx))
                return cur.fetchone() is not None or legacy_tx_used(net,tx)
            tx,sender=verify_two_source_transfer(invoice,proof_a,proof_b,tx_previously_consumed=already_used)
            evidence=hashlib.sha256(json.dumps({
                "tx_hash":tx,"network":network,"invoice_id":id_,"amount_sun":int(amount_sun),
                "sender":sender,"source_a":proof_a.source_id,"source_b":proof_b.source_id},
                sort_keys=True,separators=(",",":")).encode()).hexdigest()
            cur.execute("""INSERT INTO mpw_walletless_trx_receipt_v1
                (invoice_id,network,tx_hash,sender,evidence_sha256,confirmed_at)
                VALUES (%s,%s,%s,%s,%s,UTC_TIMESTAMP(6))""",
                (id_,network,tx,sender,evidence))
            cur.execute("""INSERT INTO mpw_walletless_trx_ledger_v1
                (invoice_id,amount_usd,asset,reference) VALUES (%s,%s,'TRX',%s)""",
                (id_,str(total_usd),tx))
            cur.execute("""INSERT INTO mpw_walletless_trx_entitlement_v1
                (invoice_id,customer_id,order_id,granted_at)
                VALUES (%s,%s,%s,UTC_TIMESTAMP(6))""",
                (id_,customer_id,order_id))
            cur.execute("""UPDATE mpw_walletless_trx_reservation_v1
                SET status='paid',verified_tx_hash=%s WHERE id=%s AND status='awaiting'""",
                (tx,id_))
            if cur.rowcount!=1:
                raise PaymentHold("Concurrent payment conflict")
        conn.commit()
        return "paid"
    except BaseException:
        conn.rollback()
        raise

def paid_entitlement_isolated(conn, *, invoice_id:int, customer_id:int)->bool:
    """Fail-closed: receipt, ledger, order ownership and grant must all exist."""
    if type(invoice_id) is not int or invoice_id<=0 or type(customer_id) is not int or customer_id<=0:
        return False
    with conn.cursor() as cur:
        cur.execute("""SELECT i.id FROM mpw_walletless_trx_reservation_v1 i
             JOIN mpw_walletless_trx_receipt_v1 r ON r.invoice_id=i.id
             JOIN mpw_walletless_trx_ledger_v1 l ON l.invoice_id=i.id
             JOIN mpw_walletless_trx_entitlement_v1 e ON e.invoice_id=i.id
             WHERE i.id=%s AND i.customer_id=%s AND e.customer_id=%s
             AND e.order_id=i.order_id AND i.status='paid'
             AND i.network='tron-mainnet' AND i.verified_tx_hash=r.tx_hash
             AND l.reference=r.tx_hash AND l.asset='TRX'
             AND l.amount_usd=i.total_usd LIMIT 1""",(invoice_id,customer_id,customer_id))
        return cur.fetchone() is not None

def candidates_for_auto_reconcile(conn, *, max_items=25):
    if type(max_items) is not int or not 1<=max_items<=50:
        raise PaymentHold("Invalid scan bound")
    with conn.cursor() as cur:
        cur.execute("""SELECT id,network,recipient,amount_sun,issued_at,expires_at
            FROM mpw_walletless_trx_reservation_v1 WHERE status='awaiting'
            ORDER BY issued_at ASC LIMIT %s""",(max_items,))
        return list(cur.fetchall())
