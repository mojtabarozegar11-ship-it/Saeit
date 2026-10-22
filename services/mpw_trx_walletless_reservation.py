"""Isolated MariaDB walletless TRX *reservation* adapter, not a payment gateway.

Only stores price-locked unpayable invoice proposals. Publishing recipient/amount
must wait until a separate independently verified chain settlement and real
Order/Ledger/CommerceFulfillment transaction are integrated and tested.
No production connection is opened by this module.
"""
from datetime import timezone, datetime
from decimal import Decimal
from typing import Callable
from services.mpw_trx_walletless_core import issue_intent, PaymentHold, NETWORK

def _dbtime(stamp):
    if not isinstance(stamp, datetime) or stamp.tzinfo is None or stamp.utcoffset() is None:
        raise PaymentHold("Timezone required")
    return stamp.astimezone(timezone.utc).replace(tzinfo=None)

def reserve_isolated(
    conn, *, order_id:int, customer_id:int, recipient:str, usd_total:Decimal,
    usd_per_trx:Decimal, quote_observed_at:datetime, now:datetime,
    random_below:Callable[[int],int], legacy_amount_reserved:Callable[[int],bool],
):
    """Reserve price with a persistent row lock, idempotent order, permanent unique amount.

    Database MUST be private TEST database. Caller MUST supply rate from trusted
    server, validate buyer ownership/product and check legacy invoice uniqueness.
    Does not create a real bill, receipt, ledger entry or access grant.
    """
    if not callable(legacy_amount_reserved):
        raise PaymentHold("Existing live invoice allocation checker unavailable")
    conn.begin()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT recipient FROM mpw_walletless_trx_allocator_v1 WHERE recipient=%s FOR UPDATE",(recipient,))
            if cursor.fetchone() is None:
                raise PaymentHold("Recipient allocation lock not provisioned")
            cursor.execute("SELECT id,customer_id,amount_sun,status FROM mpw_walletless_trx_reservation_v1 WHERE order_id=%s FOR UPDATE",(order_id,))
            existing=cursor.fetchone()
            if existing is not None:
                if int(existing[1])!=customer_id:
                    raise PaymentHold("Order belongs to different buyer")
                conn.commit()
                return int(existing[0]),int(existing[2]),False

            def exists(amount):
                cursor.execute("SELECT id FROM mpw_walletless_trx_reservation_v1 WHERE network=%s AND recipient=%s AND amount_sun=%s LIMIT 1",(NETWORK,recipient,amount))
                if cursor.fetchone() is not None:return True
                return legacy_amount_reserved(amount)
            proposal=issue_intent(
                order_id=order_id,customer_id=customer_id,recipient=recipient,
                usd_total=usd_total,usd_per_trx=usd_per_trx,quote_observed_at=quote_observed_at,
                now=now,is_amount_reserved=exists,random_below=random_below)
            cursor.execute("""INSERT INTO mpw_walletless_trx_reservation_v1
              (order_id,customer_id,network,recipient,amount_sun,total_usd,
               rate_usd_per_trx,issued_at,expires_at,status)
              VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'awaiting')""",
                (order_id,customer_id,proposal.network,recipient,proposal.amount_sun,
                 str(proposal.usd_total),str(proposal.quote_usd_per_trx),
                 _dbtime(proposal.issued_at),_dbtime(proposal.expires_at)))
            invoice_id=cursor.lastrowid
        conn.commit()
        return invoice_id,proposal.amount_sun,True
    except BaseException:
        conn.rollback()
        raise
