"""Runtime readiness is distinct from a review approval or a boolean alone."""
from django.conf import settings

def trading_runtime_ready():
    key = getattr(settings, "MPW_SIMULATION_EVENT_KEY", "")
    symbols = getattr(settings, "MPW_SIMULATION_ALLOWED_SYMBOLS", ())
    return (getattr(settings, "MPW_SIMULATION_TRADING_ENABLED", False) is True
            and callable(getattr(settings, "MPW_SIMULATION_QUOTE_PROVIDER", None))
            and isinstance(key, str) and len(key) >= 32
            and isinstance(symbols, (tuple, list)) and bool(symbols)
            and all(isinstance(symbol, str) and symbol.isascii() and 1 <= len(symbol) <= 16
                    for symbol in symbols)
            and getattr(settings, "MPW_SIMULATION_WORKER_READY", False) is True)
