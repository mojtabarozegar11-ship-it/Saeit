"""Minimal runtime policy dependency for isolated MOJ PROP persistence."""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class SimulationPolicy:
    contract_version: str = "2026-11-19/simulation-v1"
    starting_balance_usd: Decimal = Decimal("1000")
    real_orders_enabled: bool = False


SIMULATION_POLICY = SimulationPolicy()
