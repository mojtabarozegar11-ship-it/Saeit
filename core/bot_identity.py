"""Canonical product identity for the single top-level Mojtaba.bot.ai robot.

Workers, specialist agents and service processes are internal components of
this one product; this module does not stop or merge running services.
"""

BOT_ID = "mojtaba.bot.ai"
BOT_NAME = "Mojtaba.bot.ai"
_LEGACY_PUBLIC_ALIASES = frozenset({BOT_ID, "mojtaba.bot"})


def canonical_bot_id(name):
    """Resolve an explicit public robot name, rejecting unrelated identities."""
    if not isinstance(name, str):
        raise ValueError("bot identity must be text")
    normalized = name.strip().casefold()
    if normalized not in _LEGACY_PUBLIC_ALIASES:
        raise ValueError("only Mojtaba.bot.ai is an authorized public bot identity")
    return BOT_ID


def enforce_single_top_level_bot(configured_names):
    """Validate a proposed registry; never change its live DB records."""
    if not isinstance(configured_names, (tuple, list)) or len(configured_names) != 1:
        raise ValueError("exactly one top-level robot must be configured")
    return canonical_bot_id(configured_names[0])
