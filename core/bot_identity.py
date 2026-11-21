"""Canonical product identity for the single top-level Mojtaba.bot.ai robot.

Workers, specialist agents and service processes are internal components of
this one product; this module does not stop or merge running services.
"""

from mojtaba_identity import BOT_ID, BOT_NAME
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


def summarize_internal_agent_registry(rows):
    """Read-only summary of component *records*, not live process topology.

    Distinct Django Agent rows can be workers inside one product. Their count
    must never be reported as the number of public bots or deployed processes.
    """
    if not isinstance(rows, (list, tuple)):
        raise ValueError("agent rows must be a sequence")
    by_code = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("code"), str):
            raise ValueError("invalid agent record")
        code = row["code"].strip()
        if not code or code in by_code or type(row.get("active")) is not bool:
            raise ValueError("duplicate, empty or invalid agent record")
        by_code[code] = row["active"]
    return {
        "public_bot_id": BOT_ID,
        "public_bot_name": BOT_NAME,
        "declared_top_level_bot_count": 1,
        "django_component_records": len(by_code),
        "active_django_component_records": sum(by_code.values()),
        "economic_orchestrator_record_present": "economic-master-agent" in by_code,
        "economic_orchestrator_active": by_code.get("economic-master-agent", False),
        "factory_component_record_present": "moj_1ro_1" in by_code,
        "factory_component_active": by_code.get("moj_1ro_1", False),
        "runtime_process_topology_attested": False,
        "scope": "django_agent_registry_only",
    }
