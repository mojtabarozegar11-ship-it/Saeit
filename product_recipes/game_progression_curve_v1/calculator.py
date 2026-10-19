"""Deterministic offline XP progression planning."""
import math

def curve(base_xp, growth, levels, xp_per_minute):
    if type(levels) is not int or not 2 <= levels <= 200:
        raise ValueError("invalid level count")
    values = (base_xp, growth, xp_per_minute)
    if any(not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v) or v <= 0 for v in values):
        raise ValueError("invalid numeric input")
    if not 1 <= growth <= 3 or base_xp > 1000000 or xp_per_minute > 1000000:
        raise ValueError("input outside bounds")
    total = 0
    rows = []
    for level in range(1, levels):
        xp = math.ceil(base_xp * level ** growth)
        total += xp
        rows.append((level, xp, total, round(xp / xp_per_minute, 4)))
    return rows
