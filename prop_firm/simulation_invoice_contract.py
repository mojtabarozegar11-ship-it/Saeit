"""Versioned simulation offer contract; no mutation of historical invoices."""
from dataclasses import dataclass
from hashlib import sha256
import json
import re

PRODUCT_CODE = "MOJ-PROP-SIM-01"
CONTRACT_VERSION = "2026-11-19/sim-v2"
NETWORK = "tron-mainnet"
FEES_SUN = {"first": 30_000_000, "retry": 18_000_000}
REQUIRED_GATES = (
    "jurisdiction_approval", "terms_approval", "merchant_settlement_ready",
    "identity_eligibility_ready", "simulation_data_rights_verified",
    "reward_reserve_verified", "dispute_refund_ready",
    "anti_tamper_ready", "fulfillment_verified", "owner_release_approval",
)

@dataclass(frozen=True)
class SimulationInvoiceContract:
    recipient: str
    terms_digest: str
    purchase_kind: str = "first"

    def snapshot(self):
        if not isinstance(self.recipient, str) or not re.fullmatch(r"T[1-9A-HJ-NP-Za-km-z]{33}", self.recipient):
            raise ValueError("TRON recipient format invalid")
        if not isinstance(self.terms_digest, str) or not re.fullmatch(r"[0-9a-f]{64}", self.terms_digest):
            raise ValueError("Terms SHA256 required")
        if self.purchase_kind not in FEES_SUN:
            raise ValueError("Unsupported purchase kind")
        return dict(product_code=PRODUCT_CODE, contract_version=CONTRACT_VERSION,
                    network=NETWORK, recipient=self.recipient, terms_digest=self.terms_digest,
                    purchase_kind=self.purchase_kind, amount_sun=FEES_SUN[self.purchase_kind],
                    virtual_balance_usd=1000, challenge_days=60,
                    account_mode="simulated", data_mode="synthetic_replay",
                    virtual_principal_withdrawable=False)

    def digest(self):
        return sha256(json.dumps(self.snapshot(), sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    def release(self, gates, *, retry_eligibility_verified=False):
        snapshot = self.snapshot()
        if any(gates.get(name) is not True for name in REQUIRED_GATES):
            raise ValueError("Simulation release evidence incomplete")
        if self.purchase_kind == "retry" and retry_eligibility_verified is not True:
            raise ValueError("Trusted retry eligibility required")
        return snapshot
