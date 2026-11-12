"""Non-deployment supply policy for Mojoner and Moj1..Moj50.

No blockchain transaction, contract deployment or wallet operation is performed.
An unspecified network/supply is deliberately rejected, never silently chosen.
"""
from decimal import Decimal, InvalidOperation

MOJONER_SUPPLY = 24_567_856
MIN_OTHER_SUPPLY = 100_000_000_000
MAX_OTHER_SUPPLY = 10_000_000_000_000


def validate_token(name, network, supply):
    """Return a validated, explicit token configuration or raise ValueError."""
    if not isinstance(name, str) or not isinstance(network, str):
        raise ValueError("Token name and network must be strings")
    if not network.strip():
        raise ValueError("Network requires a documented, explicit selection")
    if isinstance(supply, bool) or not isinstance(supply, (int, str)):
        raise ValueError("Supply must be an exact whole-number integer")
    try:
        amount = Decimal(str(supply))
    except InvalidOperation as exc:
        raise ValueError("Invalid supply") from exc
    if not amount.is_finite() or amount != amount.to_integral_value():
        raise ValueError("Supply must be finite and integral")
    amount = int(amount)
    if name == "Mojoner":
        if network.strip().lower() != "bitcoin" or amount != MOJONER_SUPPLY:
            raise ValueError("Mojoner requires Bitcoin and exactly 24567856 units")
    elif name.startswith("Moj") and name[3:].isdigit() and 1 <= int(name[3:]) <= 50 and name == f"Moj{int(name[3:])}":
        if network.strip().lower() == "bitcoin":
            raise ValueError("Moj1..Moj50 require a non-Bitcoin network")
        if not MIN_OTHER_SUPPLY <= amount <= MAX_OTHER_SUPPLY:
            raise ValueError("Moj1..Moj50 supply outside approved range")
    else:
        raise ValueError("Unknown or noncanonical token identifier")
    return {"name": name, "network": network.strip(), "supply": amount}
