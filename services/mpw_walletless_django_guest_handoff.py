"""One-time 120-second guest claim handoff from mobile browser to TronLink DApp.

NEVER exposes 30-day signed guest cookie in URLs. The handoff URL holds only
a random 256-bit one-time bearer valid up to 120 seconds and bound to one
invoice + one real guest buyer ID. Consuming creates a DIFFERENT signed
HttpOnly cookie for the new browser; the original remains valid.
Private TEST MariaDB ONLY. Public release requires webserver access-log
token suppression and externally assessed abuse protection.
"""
from __future__ import annotations
import hashlib
import hmac
import re
import secrets
from datetime import datetime,timezone,timedelta
from django.db import transaction
from services.mpw_trx_walletless_core import PaymentHold
from services.mpw_walletless_django_guest_claim import (
    _validate_env,issue_secondary_guest_cookie_for_handoff,
)

HANDOFF_TTL=120
HEX64=re.compile(r"^[a-f0-9]{64}$")

def create_wallet_handoff(*,invoice_id:int,buyer_id:int,
                          django_settings=None,db=None)->str:
    from django.conf import settings
    from django.db import connection
    config=django_settings or settings
    conn=db or connection
    _validate_env(config,conn)
    if type(invoice_id) is not int or invoice_id<=0 or type(buyer_id) is not int or buyer_id<=0:
        raise PaymentHold("Wrong guest handoff owner")
    with transaction.atomic(using=conn.alias):
        with conn.cursor() as cur:
            cur.execute("""SELECT id FROM mpw_walletless_trx_guest_claim_v1
                           WHERE buyer_id=%s AND expires_at>UTC_TIMESTAMP(6)
                           ORDER BY id ASC LIMIT 1 FOR UPDATE""",[buyer_id])
            if cur.fetchone() is None:
                raise PaymentHold("Guest browser owner no longer valid")
            cur.execute("""SELECT customer_id,status,expires_at
                           FROM mpw_walletless_trx_reservation_v1
                           WHERE id=%s FOR UPDATE""",[invoice_id])
            info=cur.fetchone()
            if info is None or info[0]!=buyer_id or info[1]!="awaiting" or info[2]<=datetime.now(timezone.utc).replace(tzinfo=None):
                raise PaymentHold("Invoice is not available for wallet handoff")
            cur.execute("""SELECT COUNT(*) FROM mpw_walletless_trx_guest_handoff_v1
                           WHERE buyer_id=%s AND created_at>DATE_SUB(UTC_TIMESTAMP(6),INTERVAL 10 MINUTE)""",
                        [buyer_id])
            if cur.fetchone()[0]>=5:
                raise PaymentHold("Handoff generation throttled")
            token=secrets.token_hex(32)
            digest=hashlib.sha256(token.encode("ascii")).hexdigest()
            cur.execute("""INSERT INTO mpw_walletless_trx_guest_handoff_v1
                   (ticket_sha256,invoice_id,buyer_id,created_at,expires_at,consumed_at)
                   VALUES (%s,%s,%s,UTC_TIMESTAMP(6),
                      DATE_ADD(UTC_TIMESTAMP(6),INTERVAL 120 SECOND),NULL)""",
                       [digest,invoice_id,buyer_id])
    return f"/commerce/trx-easy/claim/{token}/"


def redeem_wallet_handoff(token:str,*,django_settings=None,db=None):
    """Return (invoice ID, new browser cookie) or fail closed.

    A GET invocation is acceptable ONLY because this high-entropy link itself
    is the bearer authorization, one-time, expires in two minutes, and no
    funds/account passwords move. Never log raw ticket or referrer.
    """
    from django.conf import settings
    from django.db import connection
    config=django_settings or settings
    conn=db or connection
    _validate_env(config,conn)
    if type(token) is not str or HEX64.fullmatch(token) is None:
        raise PaymentHold("Invalid wallet handoff token")
    digest=hashlib.sha256(token.encode("ascii")).hexdigest()
    with transaction.atomic(using=conn.alias):
        with conn.cursor() as cur:
            cur.execute("""SELECT invoice_id,buyer_id
                          FROM mpw_walletless_trx_guest_handoff_v1
                          WHERE ticket_sha256=%s AND consumed_at IS NULL
                          AND expires_at>UTC_TIMESTAMP(6) FOR UPDATE""",[digest])
            row=cur.fetchone()
            if row is None:
                raise PaymentHold("Expired or already-used wallet link")
            invoice_id,buyer_id=map(int,row)
            cur.execute("""SELECT id FROM mpw_walletless_trx_reservation_v1
                       WHERE id=%s AND customer_id=%s AND status='awaiting'
                       AND expires_at>UTC_TIMESTAMP(6) FOR UPDATE""",
                       [invoice_id,buyer_id])
            if cur.fetchone() is None:
                raise PaymentHold("Wallet link invoice is no longer payable")
            cur.execute("""UPDATE mpw_walletless_trx_guest_handoff_v1
                       SET consumed_at=UTC_TIMESTAMP(6)
                       WHERE ticket_sha256=%s AND consumed_at IS NULL""",[digest])
            if cur.rowcount!=1:
                raise PaymentHold("Wallet ticket concurrently consumed")
            signed_cookie=issue_secondary_guest_cookie_for_handoff(
                buyer_id,django_settings=config,db=conn)
    return invoice_id,signed_cookie
