-- Isolated walletless TRX prototype schema. Not an active production migration.
-- Every amount reservation is permanent even after expiration.
CREATE TABLE IF NOT EXISTS mpw_walletless_trx_allocator_v1 (
    recipient VARCHAR(42) PRIMARY KEY
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS mpw_walletless_trx_reservation_v1 (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    order_id BIGINT UNSIGNED NOT NULL,
    customer_id BIGINT UNSIGNED NOT NULL,
    network VARCHAR(20) NOT NULL,
    recipient VARCHAR(42) NOT NULL,
    amount_sun BIGINT UNSIGNED NOT NULL,
    total_usd DECIMAL(18,4) NOT NULL,
    rate_usd_per_trx DECIMAL(24,12) NOT NULL,
    issued_at DATETIME(6) NOT NULL,
    expires_at DATETIME(6) NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'awaiting',
    verified_tx_hash CHAR(64) NULL,
    PRIMARY KEY(id),
    UNIQUE KEY mpw_walletless_one_order(order_id),
    UNIQUE KEY mpw_walletless_unique_amount(network, recipient, amount_sun),
    UNIQUE KEY mpw_walletless_verified_tx(network, verified_tx_hash),
    KEY mpw_walletless_pending(status,issued_at)
) ENGINE=InnoDB;


-- Financial evidence belongs to the same transaction as the invoice status update.
-- Preproduction-only standalone ledger and entitlement tables. Production must
-- use Django's actual LedgerEntry and CommerceFulfillment, NOT these shadow tables.
CREATE TABLE IF NOT EXISTS mpw_walletless_trx_receipt_v1 (
  invoice_id BIGINT UNSIGNED NOT NULL,
  network VARCHAR(20) NOT NULL,
  tx_hash CHAR(64) NOT NULL,
  sender VARCHAR(42) NOT NULL,
  evidence_sha256 CHAR(64) NOT NULL,
  confirmed_at DATETIME(6) NOT NULL,
  PRIMARY KEY(invoice_id),
  UNIQUE KEY mpw_walletless_global_replay(network,tx_hash),
  CONSTRAINT mpw_walletless_receipt_invoice_fk FOREIGN KEY (invoice_id)
    REFERENCES mpw_walletless_trx_reservation_v1(id)
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS mpw_walletless_trx_ledger_v1 (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  invoice_id BIGINT UNSIGNED NOT NULL,
  amount_usd DECIMAL(18,4) NOT NULL,
  asset VARCHAR(3) NOT NULL,
  reference CHAR(64) NOT NULL,
  PRIMARY KEY(id),
  UNIQUE KEY mpw_walletless_ledger_per_invoice(invoice_id),
  UNIQUE KEY mpw_walletless_ledger_per_tx(reference),
  CONSTRAINT mpw_walletless_ledger_invoice_fk FOREIGN KEY(invoice_id)
    REFERENCES mpw_walletless_trx_reservation_v1(id)
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS mpw_walletless_trx_entitlement_v1 (
  invoice_id BIGINT UNSIGNED NOT NULL,
  customer_id BIGINT UNSIGNED NOT NULL,
  order_id BIGINT UNSIGNED NOT NULL,
  granted_at DATETIME(6) NOT NULL,
  PRIMARY KEY(invoice_id),
  UNIQUE KEY mpw_walletless_entitlement_per_order(order_id),
  CONSTRAINT mpw_walletless_entitlement_invoice_fk FOREIGN KEY(invoice_id)
    REFERENCES mpw_walletless_trx_reservation_v1(id)
) ENGINE=InnoDB;


-- Temporary guest identity proof for the isolated Django test gateway only.
-- Each guest is mapped to a distinct Django user whose password is unusable.
-- The raw cookie secret is NEVER stored in MariaDB.
CREATE TABLE IF NOT EXISTS mpw_walletless_trx_guest_claim_v1 (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  buyer_id BIGINT UNSIGNED NOT NULL,
  secret_sha256 CHAR(64) NOT NULL,
  created_at DATETIME(6) NOT NULL,
  expires_at DATETIME(6) NOT NULL,
  PRIMARY KEY(id),
  KEY mpw_walletless_guest_buyer(buyer_id),
  UNIQUE KEY mpw_walletless_guest_one_secret(secret_sha256),
  KEY mpw_walletless_guest_expiry(expires_at)
) ENGINE=InnoDB;


-- Atomic hourly registration throttle keyed by HMAC of server-observed IP.
-- No raw IP address is persisted. This is NOT a substitute for edge WAF.
CREATE TABLE IF NOT EXISTS mpw_walletless_trx_guest_rate_v1 (
  rate_key CHAR(64) NOT NULL,
  attempts INT UNSIGNED NOT NULL,
  created_at DATETIME(6) NOT NULL,
  PRIMARY KEY(rate_key)
) ENGINE=InnoDB;

-- 120-second single-use wallet-browser handoff; raw token is never stored.
-- A separately signed guest cookie is issued only AFTER ticket redemption.
CREATE TABLE IF NOT EXISTS mpw_walletless_trx_guest_handoff_v1 (
  ticket_sha256 CHAR(64) NOT NULL,
  invoice_id BIGINT UNSIGNED NOT NULL,
  buyer_id BIGINT UNSIGNED NOT NULL,
  created_at DATETIME(6) NOT NULL,
  expires_at DATETIME(6) NOT NULL,
  consumed_at DATETIME(6) NULL,
  PRIMARY KEY(ticket_sha256),
  KEY mpw_walletless_handoff_buyer_time(buyer_id,created_at),
  KEY mpw_walletless_handoff_expiry(expires_at),
  CONSTRAINT mpw_walletless_handoff_invoice_fk FOREIGN KEY(invoice_id)
     REFERENCES mpw_walletless_trx_reservation_v1(id)
) ENGINE=InnoDB;
