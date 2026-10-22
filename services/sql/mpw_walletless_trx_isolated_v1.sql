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
