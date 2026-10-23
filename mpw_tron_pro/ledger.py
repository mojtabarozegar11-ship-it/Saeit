"""Append-safe checkout ledger; transactional one-address-per-invoice allocation.

SQLite supports a single small pilot. Use PostgreSQL and owner-reviewed migrations
for multi-worker, high-throughput production. No private keys or sweep functions.
"""
from __future__ import annotations
import hashlib
import json
import re
import secrets
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from .core import CheckoutError, ExpectedTransfer, QUOTE_TTL_MS, sun_quote, tron_address_hex, verify_finalized_trx, inspect_finalized_trx

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
CREATE TABLE IF NOT EXISTS payment_observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id INTEGER NOT NULL REFERENCES invoices(id),
    txid TEXT NOT NULL UNIQUE,
    amount_sun INTEGER NOT NULL CHECK(amount_sun > 0),
    kind TEXT NOT NULL CHECK(kind IN ('underpaid','overpaid')),
    block_number INTEGER NOT NULL,
    block_ms INTEGER NOT NULL,
    recorded_ms INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_observation_invoice ON payment_observations(invoice_id, id);
CREATE TABLE IF NOT EXISTS invoice_verify_attempts (
    invoice_id INTEGER NOT NULL REFERENCES invoices(id),
    requested_ms INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_verify_attempts ON invoice_verify_attempts(invoice_id, requested_ms);
CREATE TABLE IF NOT EXISTS invoice_scan_state (
  invoice_id INTEGER PRIMARY KEY REFERENCES invoices(id),
  next_scan_ms INTEGER NOT NULL DEFAULT 0,
  last_scanned_ms INTEGER NOT NULL DEFAULT 0,
  failures INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_scan_due ON invoice_scan_state(next_scan_ms);
CREATE TABLE IF NOT EXISTS delivery_outbox (
  invoice_id INTEGER PRIMARY KEY REFERENCES invoices(id),
  event_id TEXT UNIQUE NOT NULL,
  status TEXT NOT NULL DEFAULT 'queued' CHECK(status IN ('queued','leased','delivered')),
  attempts INTEGER NOT NULL DEFAULT 0,
  next_attempt_ms INTEGER NOT NULL DEFAULT 0,
  lease_token TEXT,
  leased_until_ms INTEGER NOT NULL DEFAULT 0,
  receipt_id TEXT,
  last_error TEXT,
  created_ms INTEGER NOT NULL,
  updated_ms INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_delivery_due ON delivery_outbox(status,next_attempt_ms,leased_until_ms);

CREATE TABLE IF NOT EXISTS scan_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recorded_ms INTEGER NOT NULL,
    success INTEGER NOT NULL CHECK(success IN (0,1)),
    scanned INTEGER NOT NULL CHECK(scanned >= 0),
    settled INTEGER NOT NULL CHECK(settled >= 0),
    failures INTEGER NOT NULL CHECK(failures >= 0)
);
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

    def by_order(self, order_id: str) -> dict | None:
        if not isinstance(order_id, str) or not ORDER_ID.fullmatch(order_id):
            return None
        with self._connect() as db:
            row = db.execute('SELECT * FROM invoices WHERE merchant_order_id=?', (order_id,)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def _paid_event_id(invoice_id: int, txid: str) -> str:
        return 'mpwtr_' + hashlib.sha256(
            ('mpw:trx:paid:v1:' + str(invoice_id) + ':' + txid).encode('ascii')).hexdigest()

    def _enqueue_locked(self, db, invoice_id: int, txid: str, now_ms: int) -> None:
        # Invoice settlement and fulfillment intent are one atomic DB transaction.
        db.execute('''INSERT OR IGNORE INTO delivery_outbox
            (invoice_id,event_id,created_ms,updated_ms) VALUES(?,?,?,?)''',
            (invoice_id,self._paid_event_id(invoice_id,txid),now_ms,now_ms))

    def defer_scan(self, invoice_id: int, *, failures=0, now_ms: int | None = None):
        '''Bound fair background work. One broken old invoice must not starve new invoices.'''
        if type(invoice_id) is not int or invoice_id <= 0 or type(failures) is not int or failures < 0:
            raise CheckoutError('Invalid scan attempt')
        now = int(time.time()*1000) if now_ms is None else now_ms
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            previous = db.execute('SELECT failures FROM invoice_scan_state WHERE invoice_id=?',
                                  (invoice_id,)).fetchone()
            fails = min(10, (previous['failures'] if previous else 0) + 1) if failures else 0
            delay = min(300000, 20000 * (2 ** min(fails,4)))
            db.execute('''INSERT INTO invoice_scan_state(invoice_id,next_scan_ms,last_scanned_ms,failures)
                VALUES (?,?,?,?) ON CONFLICT(invoice_id) DO UPDATE SET
                next_scan_ms=excluded.next_scan_ms,last_scanned_ms=excluded.last_scanned_ms,
                failures=excluded.failures''', (invoice_id,now+delay,now,fails))
            db.commit()

    def fulfillment_state(self, invoice_id: int) -> str:
        with self._connect() as db:
            row=db.execute('SELECT status FROM delivery_outbox WHERE invoice_id=?', (invoice_id,)).fetchone()
        return ('delivered' if row['status']=='delivered' else 'pending_delivery') if row else 'not_integrated'

    def claim_delivery(self, *, now_ms: int | None=None) -> dict | None:
        '''Atomic lease with crash recovery and stable event IDs for idempotent merchant delivery.'''
        now = int(time.time()*1000) if now_ms is None else now_ms
        lease = secrets.token_urlsafe(32)
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('''SELECT o.*,i.merchant_order_id,i.txid,i.block_number,i.paid_ms,
                    i.amount_sun,i.address,i.usd,i.product_title
                FROM delivery_outbox o JOIN invoices i ON i.id=o.invoice_id
                WHERE i.status='paid' AND i.txid IS NOT NULL AND
                  ((o.status='queued' AND o.next_attempt_ms<=?) OR
                   (o.status='leased' AND o.leased_until_ms<=?))
                ORDER BY o.created_ms LIMIT 1''', (now,now)).fetchone()
            if row is None:
                db.rollback()
                return None
            db.execute('''UPDATE delivery_outbox SET status='leased',lease_token=?,
                leased_until_ms=?,attempts=attempts+1,updated_ms=? WHERE invoice_id=?''',
                (lease,now+120000,now,row['invoice_id']))
            db.commit()
        return {**dict(row),'lease_token':lease}

    def finish_delivery(self, invoice_id: int, lease: str, *, receipt_id=None,
                        error=None, now_ms: int | None=None):
        if type(invoice_id) is not int or invoice_id<=0 or not isinstance(lease,str):
            raise CheckoutError('Invalid delivery claim')
        if (receipt_id is None) == (error is None):
            raise CheckoutError('Exactly one delivery outcome required')
        now = int(time.time()*1000) if now_ms is None else now_ms
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('''SELECT attempts FROM delivery_outbox WHERE invoice_id=? AND
                status='leased' AND lease_token=?''', (invoice_id,lease)).fetchone()
            if row is None:
                db.rollback()
                raise CheckoutError('Delivery lease expired or changed')
            if receipt_id is not None:
                if not isinstance(receipt_id,str) or not re.fullmatch(r'[A-Za-z0-9_-]{8,128}',receipt_id):
                    db.rollback();raise CheckoutError('Invalid merchant delivery receipt')
                db.execute('''UPDATE delivery_outbox SET status='delivered',receipt_id=?,
                    lease_token=NULL,leased_until_ms=0,last_error=NULL,updated_ms=?
                    WHERE invoice_id=?''',(receipt_id,now,invoice_id))
            else:
                if not isinstance(error,str) or not re.fullmatch(r'[A-Za-z0-9_. -]{1,100}',error):
                    db.rollback();raise CheckoutError('Invalid delivery error category')
                delay=min(3600000,20000*(2**min(8,row['attempts']-1)))
                db.execute('''UPDATE delivery_outbox SET status='queued',next_attempt_ms=?,
                    lease_token=NULL,leased_until_ms=0,last_error=?,updated_ms=?
                    WHERE invoice_id=?''',(now+delay,error,now,invoice_id))
            db.commit()

    def delivery_backlog(self) -> dict:
        with self._connect() as db:
            rows=db.execute('SELECT status,COUNT(*) AS n FROM delivery_outbox GROUP BY status').fetchall()
        return {r['status']:r['n'] for r in rows}

    def record_scan_run(self, counts: dict, *, now_ms: int | None = None) -> None:
        """Persist scanner liveness, not a fabricated payment success signal."""
        now = int(time.time() * 1000) if now_ms is None else now_ms
        scanned = counts['scanned']; settled = counts['settled']
        failures = counts['failed_scans'] + counts['requires_review'] + counts.get('delivery_retry',0)
        if any(type(n) is not int or n < 0 for n in (now,scanned,settled,failures)):
            raise CheckoutError('Invalid scan counters')
        success = int(failures == 0)
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('INSERT INTO scan_runs(recorded_ms,success,scanned,settled,failures) VALUES (?,?,?,?,?)',
                       (now,success,scanned,settled,failures))
            # Bound unneeded diagnostic history; retain latest 500 runs.
            db.execute('DELETE FROM scan_runs WHERE id NOT IN (SELECT id FROM scan_runs ORDER BY id DESC LIMIT 500)')
            db.commit()

    def monitoring(self, *, now_ms: int | None = None) -> str:
        now = int(time.time() * 1000) if now_ms is None else now_ms
        with self._connect() as db:
            last = db.execute('SELECT recorded_ms,success FROM scan_runs ORDER BY id DESC LIMIT 1').fetchone()
        if last is None:
            return 'not_configured'
        if now - last['recorded_ms'] > 180000 or now < last['recorded_ms'] - 15000:
            return 'stale'
        if last['success'] != 1:
            return 'degraded'
        return 'running'

    def public_state(self, invoice: dict, *, now_ms: int | None = None) -> dict:
        """Buyer-visible settlement state from final proof, never browser claims."""
        now = int(time.time() * 1000) if now_ms is None else now_ms
        if invoice['status'] == 'paid':
            status = 'paid'
        else:
            with self._connect() as db:
                review = db.execute('''SELECT kind, amount_sun FROM payment_observations
                   WHERE invoice_id=? ORDER BY id DESC LIMIT 1''', (invoice['id'],)).fetchone()
            status = review['kind'] if review else ('expired' if now > invoice['expires_ms'] else 'pending')
        fulfillment = self.fulfillment_state(invoice['id']) if status == 'paid' else 'not_integrated'
        return {'status': status, 'expires_ms': invoice['expires_ms'],
                'server_now_ms': now, 'order_id': invoice['merchant_order_id'],
                'network': 'tron-mainnet', 'currency': 'TRX',
                'payment_confirmed': status == 'paid',
                'fulfillment': fulfillment, 'monitoring': self.monitoring(now_ms=now)}

    def allow_verification(self, invoice_id: int, *, now_ms: int | None = None) -> bool:
        """Bound invoice-triggered RPC calls: 4/minute, 24/hour."""
        now = int(time.time() * 1000) if now_ms is None else now_ms
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('DELETE FROM invoice_verify_attempts WHERE requested_ms <= ?', (now - 3600000,))
            minute = db.execute('SELECT COUNT(*) FROM invoice_verify_attempts WHERE invoice_id=? AND requested_ms>?',
                                (invoice_id, now - 60000)).fetchone()[0]
            hour = db.execute('SELECT COUNT(*) FROM invoice_verify_attempts WHERE invoice_id=? AND requested_ms>?',
                              (invoice_id, now - 3600000)).fetchone()[0]
            if minute >= 4 or hour >= 24:
                db.rollback()
                return False
            db.execute('INSERT INTO invoice_verify_attempts(invoice_id,requested_ms) VALUES (?,?)', (invoice_id, now))
            db.commit()
            return True

    def record_mismatched_payment(self, invoice_id: int, txid: str, tx: dict, receipt: dict) -> dict:
        """Record an authenticated transfer as manual review, never mark paid."""
        if type(invoice_id) is not int or invoice_id <= 0:
            raise CheckoutError('Invalid invoice')
        with self._connect() as db:
            inv = db.execute('SELECT * FROM invoices WHERE id=?', (invoice_id,)).fetchone()
        if inv is None:
            raise CheckoutError('Invoice missing')
        expected = ExpectedTransfer(txid, inv['address'], inv['amount_sun'], inv['issued_ms'], inv['expires_ms'])
        proof = inspect_finalized_trx(tx, receipt, expected)
        if proof.amount_sun == expected.amount_sun:
            raise CheckoutError('Exact payment should use settlement flow')
        kind = 'underpaid' if proof.amount_sun < expected.amount_sun else 'overpaid'
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            # Verified observation is independent of credit: no automatic top-up aggregation.
            current = db.execute('SELECT status,address,amount_sun FROM invoices WHERE id=?', (invoice_id,)).fetchone()
            if current is None or current['status'] != 'pending' or current['address'] != proof.recipient or current['amount_sun'] != expected.amount_sun:
                db.rollback()
                raise CheckoutError('Invoice changed while recording mismatch')
            present = db.execute('SELECT invoice_id FROM payment_observations WHERE txid=?', (txid,)).fetchone()
            if present is not None:
                db.rollback()
                if present['invoice_id'] != invoice_id:
                    raise CheckoutError('Payment already assigned elsewhere')
                return {'status': kind, 'amount_sun': proof.amount_sun, 'new': False}
            db.execute('''INSERT INTO payment_observations(invoice_id,txid,amount_sun,kind,block_number,block_ms,recorded_ms)
                VALUES(?,?,?,?,?,?,?)''', (invoice_id,txid,proof.amount_sun,kind,proof.block_number,proof.block_ms,int(time.time()*1000)))
            db.commit()
        return {'status': kind, 'amount_sun': proof.amount_sun, 'new': True}

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
                self._enqueue_locked(db,invoice['id'],proof.txid,int(time.time()*1000))
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
                self._enqueue_locked(db,invoice_id,proof.txid,int(time.time()*1000))
                db.commit()
                return dict(db.execute('SELECT * FROM invoices WHERE id=?', (invoice_id,)).fetchone())
            except Exception:
                db.rollback()
                raise

    def pending(self, *, limit=30, now_ms: int | None=None) -> list[dict]:
        if type(limit) is not int or not 1 <= limit <= 100:
            raise CheckoutError('Invalid scan limit')
        now = int(time.time()*1000) if now_ms is None else now_ms
        with self._connect() as db:
            return [dict(row) for row in db.execute('''SELECT i.* FROM invoices i
                LEFT JOIN invoice_scan_state s ON s.invoice_id=i.id
                WHERE i.status='pending' AND COALESCE(s.next_scan_ms,0)<=?
                ORDER BY COALESCE(s.last_scanned_ms,0),i.issued_ms LIMIT ?''', (now,limit))]