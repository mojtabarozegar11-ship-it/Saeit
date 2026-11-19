"""Private atomic replay registry for Plan 1 independent contract reviews.

No network, customer PII, invoices, payments, enrollment or account activation.
Use a private durable SQLite database (not the public repository). A successful
claim is a review-only event; legal/KYC/funding checks remain separate.
"""
import re
import sqlite3

_REVIEW = re.compile(r"PROP1-REVIEW-[A-F0-9]{32}\Z")
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")


class ReviewReplayClosed(ValueError):
    """Missing durable storage, invalid evidence, or duplicate review."""


def claim_review_once(connection, *, review_ref, acceptance_sha256,
                      reviewer_attestation_sha256):
    """Atomically claim a unique review and acceptance pair.

    Connection must be a private, persistent sqlite3.Connection; caller owns
    its lifecycle. No table is silently created: schema installation is a
    separate controlled migration. A claim never authorizes commerce.
    """
    if not isinstance(connection, sqlite3.Connection):
        raise ReviewReplayClosed("private durable review registry required")
    if (type(review_ref) is not str or _REVIEW.fullmatch(review_ref) is None
            or any(type(v) is not str or _DIGEST.fullmatch(v) is None
                   or v == "0" * 64
                   for v in (acceptance_sha256, reviewer_attestation_sha256))
            or acceptance_sha256 == reviewer_attestation_sha256):
        raise ReviewReplayClosed("invalid independent review provenance")
    # Memory and temporary databases lose claims on restart.
    # A replay claim must survive connection closure.
    try:
        databases = connection.execute("PRAGMA database_list").fetchall()
        main_paths = [path for _, name, path in databases if name == "main"]
        if len(main_paths) != 1 or not main_paths[0]:
            raise ReviewReplayClosed("persistent private review registry required")
        journal_mode = connection.execute("PRAGMA main.journal_mode").fetchone()
        sync_mode = connection.execute("PRAGMA main.synchronous").fetchone()
        if (not journal_mode or journal_mode[0].lower() in ("off", "memory")
                or not sync_mode or sync_mode[0] < 2):
            raise ReviewReplayClosed("durable journal configuration required")
    except sqlite3.Error:
        raise ReviewReplayClosed("private review registry unavailable") from None
    if connection.in_transaction:
        raise ReviewReplayClosed("review registry connection already in a transaction")
    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            "INSERT INTO prop1_review_claims "
            "(review_ref, acceptance_sha256, reviewer_attestation_sha256) "
            "VALUES (?, ?, ?)",
            (review_ref, acceptance_sha256, reviewer_attestation_sha256),
        )
        connection.commit()
    except (sqlite3.Error, ValueError) as exc:
        if connection.in_transaction:
            connection.rollback()
        raise ReviewReplayClosed("review claim unavailable or already consumed") from None
    return "PRIVATE_REVIEW_CLAIMED_ONLY"


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS prop1_review_claims (
    review_ref TEXT PRIMARY KEY,
    acceptance_sha256 TEXT NOT NULL UNIQUE,
    reviewer_attestation_sha256 TEXT NOT NULL UNIQUE
);
"""
