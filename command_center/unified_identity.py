"""Single public robot identity and lossless read-only legacy module projection.

Old Django Agent rows are historical/operational source records, not claims of
separately branded robots or evidence of integration with this runtime.
"""

from ava_core.identity import BOT_ID


def public_bot_identity():
    """One public identity; live module execution is not attested here."""
    return {"identity": BOT_ID, "identity_count": 1,
            "runtime_verified": None, "integration_state": "unverified"}


def legacy_modules(rows):
    """Project source records as modules without inventing a live integration."""
    result = []
    for row in rows:
        result.append({
            "id": row["id"],
            "module_code": row["code"],
            "source_name": row["name"],
            "mission": row["mission"],
            "risk_level": row["risk_level"],
            "source_active": row["active"],
            "integration_verified": None,
            "verification_state": "unknown",
        })
    return result


def identity_snapshot(rows, total, *, offset=0):
    """One identity, any number of source modules, no unverified 'connected' flag."""
    if offset < 0 or total < 0:
        raise ValueError("Invalid module page")
    modules = legacy_modules(rows)
    next_offset = offset + len(modules)
    return {
        "bot": public_bot_identity(),
        "modules": modules,
        "source_module_total": total,
        "truncated": total > next_offset,
        "next_offset": next_offset if next_offset < total and modules else None,
        "changes_require_approval": True,
    }
