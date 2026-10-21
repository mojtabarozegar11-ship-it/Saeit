"""Append-safe checkout ledger; transactional one-address-per-invoice allocation.

SQLite supports a single small pilot. Use PostgreSQL and owner-reviewed migrations
for multi-worker, high-throughput production. No private keys or sweep functions.
"""
from __future__ import annotations
import hashlib
import re
import secrets
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from .core import CheckoutError, ExpectedTransfer, QUOTE_TTL_MS, sun_quote, tron_address_hex, verify_finalized_trx

ORDER_ID = re.compile(r'^[A-Za-z0-9_-]{10,80}$')

SCHEMA = '''
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS deposit_addresses (
    address TEXT PRIMARY KEY, added_ms INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    merchant_order_id TEXT UNIQUE NOT NULL,
    product_title TEXT NOT NULL,
    usd TEXT NOT NULL,
    rate TEXT NOT NULL,
    amount_sun INTEGER NOT NULL,
    address TEXT UNIQUE NOT NULL REFERENCES deposit_addresses(address),
    bearer_hash TEXT UNIQUE NOT NULL,
    issued_ms INTEGER NOT NULL,
    expires_ms INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','paid')),
    txid TEXT UNIQUE,
    block_number INTEGER,
    paid_ms INTEGER
);
CREATE INDEX IF NOT EXISTS ix_invoice_status ON invoices(status, expires_ms);
'''


@dataclass(frozen=True)
class IssuedInvoice:
    token: str
    order_id: str
    product_title: str
    usd: str
    rate: str
    amount_sun: int
    address: str
    issued_ms: int
    expires_ms: int
    status: str = 'pending'
    txid: str | None = None
    paid_ms: int | None = None


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode('ascii')).hexdigest()


class InvoiceLedger:
    def __init__(self, filename: str | Path):
        self.filename = str(filename)

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(self.filename, timeout=10, isolation_level=None)
        try:
            db.row_factory = sqlite3.Row
            db.execute('PRAGMA foreign_keys=ON')
            db.execute('PRAGMA busy_timeout=10000')
            yield db
        finally:
            db.close()

    def initialize(self):
        with self._connect() as db:
            db.executescript(SCHEMA)

    def add_public_address(self, address: str):
        tron_address_hex(address)
        with self._connect() as db:
            db.execute('INSERT INTO deposit_addresses(address,added_ms) VALUES (?,?)',
                       (address, int(time.time() * 1000)))

    def issue(self, *, merchant_order_id: str, product_title: str, usd: str,
              usd_per_trx: str, now_ms: int | None = None) -> IssuedInvoice:
        if not isinstance(merchant_order_id, str) or not ORDER_ID.fullmatch(merchant_order_id):
            raise CheckoutError('Invalid order identifier')
        if (not isinstance(product_title, str) or not 1 <= len(product_title) <= 120 or
                any(ord(c) < 32 for c in product_title)):
            raise CheckoutError('Invalid product title')
        sun = sun_quote(usd, usd_per_trx)
        now = int(time.time() * 1000) if now_ms is None else now_ms
        if type(now) is not int or now <= 0:
            raise CheckoutError('Invalid invoice timestamp')
        bearer = secrets.token_urlsafe(36)
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                if db.execute('SELECT 1 FROM invoices WHERE merchant_order_id=?',
                              (merchant_order_id,)).fetchone():
                    raise CheckoutError('Order already has an invoice')
                candidate = db.execute('''SELECT address FROM deposit_addresses
                    WHERE address NOT IN (SELECT address FROM invoices)
                    ORDER BY added_ms, address LIMIT 1''').fetchone()
                if candidate is None:
                    raise CheckoutError('No unique merchant-controlled deposit addresses available')
                db.execute('''INSERT INTO invoices
                    (merchant_order_id,product_title,usd,rate,amount_sun,address,bearer_hash,issued_ms,expires_ms)
                    VALUES (?,?,?,?,?,?,?,?,?)''',
                    (merchant_order_id, product_title, str(usd), str(usd_per_trx), sun,
                     candidate['address'], token_digest(bearer), now, now + QUOTE_TTL_MS))
                db.commit()
            except Exception:
                db.rollback()
                raise
        return IssuedInvoice(bearer, merchant_order_id, product_title, str(usd),
                             str(usd_per_trx), sun, candidate['address'], now, now + QUOTE_TTL_MS)

    def by_token(self, bearer: str) -> dict | None:
        if not isinstance(bearer, str) or not re.fullmatch(r'[A-Za-z0-9_-]{40,100}', bearer):
            return None
        with self._connect() as db:
            row = db.execute('SELECT * FROM invoices WHERE bearer_hash=?',
                             (token_digest(bearer),)).fetchone()
            return dict(row) if row else None

    def apply_proof(self, bearer: str, txid: str, tx: dict, receipt: dict) -> dict:
        invoice = self.by_token(bearer)
        if invoice is None:
            raise CheckoutError('Unknown invoice capability')
        if invoice['status'] == 'paid':
            if invoice['txid'] == txid:
                return invoice  # an idempotent retry of the SAME payment
            raise CheckoutError('Invoice already settled')
        expected = ExpectedTransfer(txid=txid, address=invoice['address'],
                                    amount_sun=invoice['amount_sun'],
                                    issued_ms=invoice['issued_ms'], expires_ms=invoice['expires_ms'])
        proof = verify_finalized_trx(tx, receipt, expected)
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                current = db.execute('SELECT * FROM invoices WHERE id=?', (invoice['id'],)).fetchone()
                if current['status'] != 'pending' or current['address'] != proof.recipient:
                    raise CheckoutError('Invoice state changed while checking payment')
                try:
                    changed = db.execute('''UPDATE invoices SET status='paid', txid=?, block_number=?, paid_ms=?
                        WHERE id=? AND status='pending' AND txid IS NULL''',
                        (proof.txid, proof.block_number, proof.block_ms, invoice['id']))
                except sqlite3.IntegrityError as exc:
                    raise CheckoutError('Transaction already claimed') from exc
                if changed.rowcount != 1:
                    raise CheckoutError('Concurrent settlement rejected')
                db.commit()
                return dict(db.execute('SELECT * FROM invoices WHERE id=?',
                                       (invoice['id'],)).fetchone())
            except Exception:
                db.rollback()
                raise

    def settle_discovered(self, invoice_id: int, txid: str, tx: dict, receipt: dict) -> dict:
        """Server-only background reconciliation without exposing buyer capability.

        Proof is computed OUTSIDE the write lock; atomic state check revalidates
        the same original address and expected amount before marking paid.
        """
        if type(invoice_id) is not int or invoice_id <= 0:
            raise CheckoutError('Invalid internal invoice identifier')
        with self._connect() as db:
            row = db.execute('SELECT * FROM invoices WHERE id=?', (invoice_id,)).fetchone()
        if row is None:
            raise CheckoutError('Invoice missing')
        invoice = dict(row)
        expected = ExpectedTransfer(txid, invoice['address'], invoice['amount_sun'],
                                    invoice['issued_ms'], invoice['expires_ms'])
        proof = verify_finalized_trx(tx, receipt, expected)
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                current = db.execute('SELECT * FROM invoices WHERE id=?', (invoice_id,)).fetchone()
                if current is None or current['address'] != proof.recipient or current['amount_sun'] != proof.amount_sun:
                    raise CheckoutError('Invoice proof no longer matches original quote')
                if current['status'] == 'paid':
                    if current['txid'] == txid:
                        db.rollback()
                        return dict(current)
                    raise CheckoutError('Invoice already settled with a different payment')
                try:
                    changed = db.execute("""UPDATE invoices SET status='paid', txid=?,block_number=?,paid_ms=?
                        WHERE id=? AND status='pending' AND txid IS NULL""",
                        (proof.txid, proof.block_number, proof.block_ms, invoice_id))
                except sqlite3.IntegrityError as exc:
                    raise CheckoutError('Discovered transaction already claimed') from exc
                if changed.rowcount != 1:
                    raise CheckoutError('Invoice concurrently changed')
                db.commit()
                return dict(db.execute('SELECT * FROM invoices WHERE id=?', (invoice_id,)).fetchone())
            except Exception:
                db.rollback()
                raise

    def pending(self, *, limit=30) -> list[dict]:
        if type(limit) is not int or not 1 <= limit <= 100:
            raise CheckoutError('Invalid scan limit')
        with self._connect() as db:
            return [dict(row) for row in db.execute(
                "SELECT * FROM invoices WHERE status='pending' ORDER BY issued_ms LIMIT ?", (limit,))]