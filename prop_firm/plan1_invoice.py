"""Fail-closed contract boundary for the real MOJ-PROP-01 Plan 1 offer.

This module has no network, database, email, wallet or broker side effect.
It only proves that a caller supplied every independent release gate.
"""
from dataclasses import dataclass
from decimal import Decimal
from hashlib import sha256
from typing import Mapping

PRODUCT_CODE = "MOJ-PROP-01"
CONTRACT_VERSION = "2026-11-15/v1.2"
NETWORK = "tron-mainnet"
AMOUNT_SUN = 30_000_000
REQUIRED_GATES = (
    "independent_capital_proof",
    "jurisdiction_approval",
    "broker_contract",
    "merchant_settlement_ready",
    "kyc_eligibility_ready",
    "owner_canary_complete",
)


@dataclass(frozen=True)
class Plan1InvoiceContract:
    product_code: str = PRODUCT_CODE
    contract_version: str = CONTRACT_VERSION
    network: str = NETWORK
    amount_sun: int = AMOUNT_SUN
    recipient: str = ""
    terms_digest: str = ""

    def digest(self) -> str:
        canonical = "|".join((
            self.product_code,
            self.contract_version,
            self.network,
            str(self.amount_sun),
            self.recipient,
            self.terms_digest,
        ))
        return sha256(canonical.encode("utf-8")).hexdigest()

    def release(self, gates: Mapping[str, bool]) -> "Plan1InvoiceContract":
        missing = [name for name in REQUIRED_GATES if gates.get(name) is not True]
        if missing:
            raise RuntimeError("MOJ-PROP-01 release blocked: " + ",".join(missing))
        if self.amount_sun != AMOUNT_SUN or self.network != NETWORK:
            raise RuntimeError("Plan 1 contract amount or network drift")
        if not self.recipient or len(self.recipient) < 10:
            raise RuntimeError("A verified TRON recipient is required")
        if len(self.terms_digest) != 64:
            raise RuntimeError("Trusted terms digest is required")
        return self
