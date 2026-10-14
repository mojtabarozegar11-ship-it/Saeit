"""Isolated staging-only ledger for native ETH/TRX chess invoices.

NEVER point this SQLite database at the live Django system or expose it as a
production checkout. A production adapter must first be reconciled with the
existing Django Order, CryptoPaymentIntent and paid-download gates.

All operations are idempotent or fail closed. A settled chain transaction cannot
be claimed by two different orders and a quoted payment amount cannot be
allocated to two orders on the same chain and receive address.
"""
import sqlite3
from dataclasses import asdict
from pathlib import Path
from typing import Callable

from mojplaywin_direct_wallet_invoice import DirectInvoice, NETWORKS, PRODUCT_ID
from mojplaywin_native_chain_verify import (
    LockedQuote, verify_eth_transfer, verify_trx_transfer,
)


class LedgerError(ValueError):
    pass


SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS invoices(
    order_id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL CHECK(product_id=72),
    asset TEXT NOT NULL CHECK(asset IN ('ETH','TRX')),
    chain TEXT NOT NULL,
    recipient TEXT NOT NULL,
    sender TEXT NOT NULL,
    units INTEGER NOT NULL CHECK(units>0),
    usd TEXT NOT NULL CHECK(usd='7.50'),
    provider TEXT NOT NULL,
    issued_at INTEGER NOT NULL,
    expires_at INTEGER NOT NULL,
    sender_verified INTEGER NOT NULL CHECK(sender_verified=1),
    status TEXT NOT NULL DEFAULT 'awaiting' CHECK(status IN ('awaiting','paid')),
    transaction_hash TEXT,
    proof_detail TEXT,
    UNIQUE(chain,recipient,units)
);
CREATE TABLE IF NOT EXISTS transactions(
    chain TEXT NOT NULL,
    tx_hash TEXT NOT NULL,
    order_id INTEGER NOT NULL UNIQUE REFERENCES invoices(order_id),
    PRIMARY KEY(chain,tx_hash)
);
"""


class StagingLedger:
    def __init__(self, file_path):
        self.file_path = str(file_path)
        if self.file_path == ":memory:":
            raise LedgerError("Use a persistent staging database, not in-memory")
        Path(self.file_path).parent.mkdir(parents=True, exist_ok=True)

    def connect(self):
        db = sqlite3.connect(self.file_path, timeout=8, isolation_level=None)
        db.row_factory=sqlite3.Row
        db.execute("PRAGMA busy_timeout=8000")
        db.execute("PRAGMA foreign_keys=ON")
        return db

    def initialize(self):
        with self.connect() as db:
            db.executescript(SCHEMA)

    @staticmethod
    def _ensure_invoice(q):
        if not isinstance(q, DirectInvoice):
            raise LedgerError("Only an approved server invoice can be staged")
        if type(q.order_id) is not int or q.order_id <= 0:
            raise LedgerError("Invalid order identifier")
        if type(q.customer_id) is not int or q.customer_id <= 0:
            raise LedgerError("Invalid customer")
        if q.product_id != PRODUCT_ID or q.quote_price_usd != "7.50":
            raise LedgerError("Wrong product or fiat price")
        if q.asset not in NETWORKS:
            raise LedgerError("Unknown coin")
        config=NETWORKS[q.asset]
        if q.chain != config["chain"] or q.recipient != config["recipient"]:
            raise LedgerError("Wrong chain or merchant address")
        if type(q.amount_smallest_units) is not int or q.amount_smallest_units <= 0:
            raise LedgerError("Invalid asset amount")
        if q.sender_proof_verified is not True:
            raise LedgerError("Sender signature has not been verified")
        if not q.expected_sender or not isinstance(q.expected_sender,str):
            raise LedgerError("Missing sender")
        if type(q.issued_at_epoch) is not int or type(q.expires_at_epoch) is not int:
            raise LedgerError("Bad invoice timestamps")
        if q.issued_at_epoch<=0 or q.expires_at_epoch-q.issued_at_epoch != 600:
            raise LedgerError("Only 10-minute invoices can be registered")

    def register_invoice(self, invoice: DirectInvoice):
        """Atomic reservation. No credit, wallet transfer, or PDF fulfilment."""
        self._ensure_invoice(invoice)
        with self.connect() as db:
            try:
                db.execute("BEGIN IMMEDIATE")
                db.execute(
                    """INSERT INTO invoices (
                        order_id,customer_id,product_id,asset,chain,recipient,
                        sender,units,usd,provider,issued_at,expires_at,sender_verified
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        invoice.order_id,invoice.customer_id,invoice.product_id,
                        invoice.asset,invoice.chain,invoice.recipient,
                        invoice.expected_sender,invoice.amount_smallest_units,
                        invoice.quote_price_usd,invoice.quote_provider,
                        invoice.issued_at_epoch,invoice.expires_at_epoch,
                        1 if invoice.sender_proof_verified else 0
                    )
                )
                db.execute("COMMIT")
            except sqlite3.IntegrityError as exc:
                db.execute("ROLLBACK")
                raise LedgerError("Order or chain amount has already been reserved") from exc
        return "awaiting"

    def get(self, order_id):
        with self.connect() as db:
            row=db.execute("SELECT * FROM invoices WHERE order_id=?",(order_id,)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def _locked_quote(row):
        return LockedQuote(
            order_id=row["order_id"],
            network=row["chain"],
            smallest_units=row["units"],
            expected_sender=row["sender"],
            created_at_ms=row["issued_at"]*1000,
            expires_at_ms=row["expires_at"]*1000,
        )

    def settle_verified_transfer(self, order_id, tx_hash, *,
                                 ethereum_rpc=None, tron_solidity_rpc=None):
        """Settle ONLY after calling the installed trusted blockchain verifier.

        RPC callbacks must be configured by the backend; never taken from a
        customer URL, browser input or third-party payment screenshot.
        The caller must reconcile any paid result into production through
        an independently reviewed integration, NOT by flipping Django status.
        """
        row=self.get(order_id)
        if row is None:
            raise LedgerError("Order not found")
        if row["status"] == "paid":
            if row["transaction_hash"] == tx_hash.lower():
                return "already_paid"
            raise LedgerError("Order is already paid with another transaction")
        q=self._locked_quote(row)
        if row["chain"]=="ethereum-mainnet":
            if ethereum_rpc is None: raise LedgerError("ETH verification provider missing")
            proof=verify_eth_transfer(tx_hash,q,ethereum_rpc)
        elif row["chain"]=="tron-mainnet":
            if tron_solidity_rpc is None: raise LedgerError("TRON solidity provider missing")
            proof=verify_trx_transfer(tx_hash,q,tron_solidity_rpc)
        else:
            raise LedgerError("Unsupported chain")
        # Blockchain verification occurs before an exclusive DB lock. Re-check
        # the immutable quote under the lock before recording a transaction.
        with self.connect() as db:
            try:
                db.execute("BEGIN IMMEDIATE")
                current=db.execute("SELECT * FROM invoices WHERE order_id=?",(order_id,)).fetchone()
                if current is None or current["status"] != "awaiting":
                    raise LedgerError("Invoice is no longer awaiting a payment")
                columns=("customer_id","asset","chain","recipient","sender",
                         "units","issued_at","expires_at")
                if any(current[k]!=row[k] for k in columns):
                    raise LedgerError("Invoice changed after verification")
                tx_canonical=tx_hash.lower()
                db.execute(
                    "INSERT INTO transactions(chain,tx_hash,order_id) VALUES(?,?,?)",
                    (row["chain"],tx_canonical,order_id)
                )
                cursor=db.execute(
                    """UPDATE invoices SET status='paid',transaction_hash=?,
                       proof_detail=? WHERE order_id=? AND status='awaiting'""",
                    (tx_canonical,str(proof),order_id)
                )
                if cursor.rowcount!=1:
                    raise LedgerError("Concurrent settlement prevented")
                db.execute("COMMIT")
            except (sqlite3.IntegrityError,LedgerError) as exc:
                db.execute("ROLLBACK")
                raise LedgerError("Duplicate transfer, or unsafe settlement") from exc
        return "paid_in_staging_only"
