"""MojPlayWin unregistered-buyer order vault (STAGING ONLY; cannot charge/fulfill).

Pure sqlite, no Django user or subscription. Exactly one immutable USD order,
one bound provider invoice, one private claim, and bounded expiration.
This package NEVER captures a charge, marks an order paid or grants a download.
Deploy only after licensed provider activation and end-to-end security review.
"""
import hashlib
import hmac
import re
import secrets
import sqlite3
import time
from decimal import Decimal, InvalidOperation

from .provider_adapter import _official_invoice_url

ORDER_TTL_SECONDS = 15 * 60
ORDER_ID = re.compile(r"^MPWF-[0-9a-f]{36}$")
INVOICE_ID = re.compile(r"^[0-9]{1,22}$")

class GuestOrderError(ValueError):
    pass

def initialize(db):
    """Caller must configure sqlite db path/permissions and backups privately."""
    db.execute("""CREATE TABLE IF NOT EXISTS fiat_guest_orders(
        order_id TEXT PRIMARY KEY,
        product_id INTEGER NOT NULL CHECK(product_id > 0),
        price_usd TEXT NOT NULL,
        client_nonce_digest TEXT NOT NULL UNIQUE,
        claim_digest TEXT NOT NULL UNIQUE,
        created_at INTEGER NOT NULL,
        expires_at INTEGER NOT NULL,
        invoice_id TEXT UNIQUE,
        invoice_url TEXT,
        state TEXT NOT NULL DEFAULT 'created'
          CHECK(state IN ('created','awaiting_payment'))
    )""")

def _parse_price(value):
    try:
        p = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise GuestOrderError("Invalid USD price") from exc
    if (not p.is_finite() or p <= 0 or p > 1000 or
            p != p.quantize(Decimal("0.01"))):
        raise GuestOrderError("Price must be exact positive cents")
    return f"{p:.2f}"

def _fingerprint(value, name):
    if not isinstance(value, str) or not 24 <= len(value) <= 256:
        raise GuestOrderError("Missing or unsafe " + name)
    if not re.fullmatch(r"[A-Za-z0-9_-]{24,256}", value):
        raise GuestOrderError("Invalid " + name)
    return hashlib.sha256(value.encode("ascii")).hexdigest()

def _utc_second(now):
    if type(now) is not int or not 0 <= now <= 9999999999:
        raise GuestOrderError("Invalid wall-clock timestamp")
    return now

def create_order(db, *, product_id, price_usd, client_nonce, now=None,
                 previous_claim=None):
    """Trusted-internal order creator. Browser MUST NOT control the product price.

    Safe retry returns the bearer claim only if the browser already knows it.
    Normal no-claim retries never mint or disclose a new private claim.
    """
    if type(product_id) is not int or not 0 < product_id <= 100000000:
        raise GuestOrderError("Invalid product")
    amount = _parse_price(price_usd)
    nonce_sha = _fingerprint(client_nonce, "client idempotency nonce")
    clock = _utc_second(int(time.time()) if now is None else now)
    claim = secrets.token_urlsafe(40)  # 320 bits, shown to browser only once
    digest = _fingerprint(claim, "buyer claim")
    order_id = "MPWF-" + secrets.token_hex(18)
    db.execute("BEGIN IMMEDIATE")
    try:
        # Prune only abandoned, never-invoiced orders; do not destroy evidence
        # for paid, disputed, or provider-issued invoices.
        db.execute("DELETE FROM fiat_guest_orders WHERE state='created' "
                   "AND invoice_id IS NULL AND expires_at<?", (clock-86400,))
        existing = db.execute(
            "SELECT order_id,product_id,price_usd,expires_at,claim_digest FROM fiat_guest_orders "
            "WHERE client_nonce_digest=?", (nonce_sha,)
        ).fetchone()
        if existing:
            if existing[1] != product_id or existing[2] != amount:
                raise GuestOrderError("Idempotency key cannot change product or price")
            recovered = None
            if previous_claim is not None:
                supplied = _fingerprint(previous_claim, "buyer claim")
                if not hmac.compare_digest(existing[4], supplied):
                    raise GuestOrderError("Cannot recover order without valid private claim")
                recovered = previous_claim
            db.commit()
            return {"order_id": existing[0], "claim": recovered,
                    "reused": True, "expires_at": existing[3]}
        pending = db.execute(
            "SELECT count(*) FROM fiat_guest_orders WHERE expires_at>? "
            "AND state IN ('created','awaiting_payment')", (clock,)
        ).fetchone()[0]
        if pending >= 1200:
            raise GuestOrderError("Guest checkout is temporarily at capacity")
        db.execute(
            "INSERT INTO fiat_guest_orders "
            "(order_id,product_id,price_usd,client_nonce_digest,claim_digest,created_at,expires_at) "
            "VALUES(?,?,?,?,?,?,?)",
            (order_id, product_id, amount, nonce_sha, digest, clock,
             clock + ORDER_TTL_SECONDS),
        )
        db.commit()
        return {"order_id": order_id, "claim": claim, "reused": False,
                "expires_at": clock + ORDER_TTL_SECONDS}
    except BaseException:
        db.rollback()
        raise


def create_catalog_order(db, *, product_id, client_nonce, trusted_catalog_quote,
                         now=None, previous_claim=None):
    """Server-only catalog boundary: never accept client-supplied prices.

    Caller must supply a trusted product lookup backed by the production catalog,
    asset/license/QC publication gates, and approved currency. This callable is
    never allowed to be a callback controlled by an HTTP request.
    """
    if type(product_id) is not int or not 0 < product_id <= 100000000:
        raise GuestOrderError("Invalid product")
    if not callable(trusted_catalog_quote):
        raise GuestOrderError("Trusted catalog quote required")
    quote = trusted_catalog_quote(product_id)
    if (type(quote) is not dict or quote.get("approved") is not True or
            quote.get("currency") != "USD" or
            type(quote.get("product_id")) is not int or
            quote["product_id"] != product_id):
        raise GuestOrderError("Product is not approved for merchant guest checkout")
    return create_order(
        db, product_id=product_id, price_usd=quote.get("price_usd"),
        client_nonce=client_nonce, now=now, previous_claim=previous_claim,
    )

def _private_order(db, order_id, claim):
    if not isinstance(order_id, str) or not ORDER_ID.fullmatch(order_id):
        raise GuestOrderError("Invalid private order identifier")
    digest = _fingerprint(claim, "buyer claim")
    row = db.execute(
        "SELECT order_id,product_id,price_usd,claim_digest,created_at,expires_at,"
        "invoice_id,invoice_url,state FROM fiat_guest_orders WHERE order_id=?",
        (order_id,),
    ).fetchone()
    if not row or not hmac.compare_digest(row[3], digest):
        raise GuestOrderError("Order not found or private claim invalid")
    return row

def status(db, *, order_id, claim, now=None):
    """Return privacy-preserving metadata; NEVER treat this as paid entitlement."""
    clock = _utc_second(int(time.time()) if now is None else now)
    row = _private_order(db, order_id, claim)
    return {"order_id": row[0], "product_id": row[1], "price_usd": row[2],
            "expires_at": row[5], "expired": clock >= row[5],
            "state": "expired" if clock >= row[5] else row[8],
            "invoice_id": row[6], "has_invoice": row[6] is not None,
            "safe_to_fulfill": False}

def bind_invoice(db, *, order_id, claim, invoice_id, invoice_url, now=None):
    """Bind official provider invoice once; same response is safely idempotent."""
    clock = _utc_second(int(time.time()) if now is None else now)
    if type(invoice_id) not in (int, str) or not INVOICE_ID.fullmatch(str(invoice_id)):
        raise GuestOrderError("Invalid provider invoice id")
    try:
        url = _official_invoice_url(invoice_url)
    except Exception as exc:
        raise GuestOrderError("Unsafe provider invoice URL") from exc
    db.execute("BEGIN IMMEDIATE")
    try:
        row = _private_order(db, order_id, claim)
        if clock >= row[5]:
            raise GuestOrderError("Expired checkout cannot be rebound")
        if row[6] is not None:
            if row[6] != str(invoice_id) or row[7] != url:
                raise GuestOrderError("Attempt to replace immutable invoice")
            db.commit()
            return {"order_id": order_id, "invoice_id": str(invoice_id),
                    "reused": True, "safe_to_fulfill": False}
        try:
            db.execute("UPDATE fiat_guest_orders SET invoice_id=?,invoice_url=?,"
                       "state='awaiting_payment' WHERE order_id=? AND invoice_id IS NULL",
                       (str(invoice_id), url, order_id))
        except sqlite3.IntegrityError as exc:
            raise GuestOrderError("Invoice assigned to another order") from exc
        db.commit()
        return {"order_id": order_id, "invoice_id": str(invoice_id),
                "reused": False, "safe_to_fulfill": False}
    except BaseException:
        db.rollback()
        raise
