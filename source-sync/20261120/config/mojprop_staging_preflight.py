"""Pure configuration preflight for the isolated MOJ PROP staging cutover.

This module deliberately performs no database connection and no migration. It
turns missing safety evidence into explicit blockers before an operator can
wire the English route to the dedicated alias.
"""

from dataclasses import dataclass
from typing import Any, Mapping

MOJPROP_DB_ALIAS = "mojprop"
MOJPROP_ROUTER_IMPORT = "config.mojprop_db_router.MojPropDatabaseRouter"

CLOSED_MOJPROP_ROUTE_FLAGS = (
    "MPW_MOJPROP_PLAN1_ROUTE_ENABLED",
    "MPW_MOJPROP_PLAN1_LIVE_INVOICE_ENABLED",
    "MPW_MOJPROP_ENGLISH_ROUTE_ENABLED",
)


@dataclass(frozen=True)
class StagingPreflight:
    """A deterministic result that can be logged without exposing secrets."""

    ready: bool
    checks: tuple[str, ...]
    blockers: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "ready": self.ready,
            "checks": list(self.checks),
            "blockers": list(self.blockers),
        }


def evaluate_staging_preflight(
    config: Mapping[str, Any],
    *,
    migration_admin_verified: bool = False,
    runtime_dml_verified: bool = False,
) -> StagingPreflight:
    """Evaluate cutover prerequisites without opening a database connection.

    The two privilege arguments are explicit operator evidence inputs. They
    default to false so configuration presence cannot be mistaken for proof.
    """

    checks: list[str] = []
    blockers: list[str] = []

    if not bool(config.get("MPW_MOJPROP_DB_ALIAS_ENABLED", False)):
        blockers.append("MOJ PROP database alias switch is not enabled for staging")
    else:
        checks.append("MOJ PROP database alias switch is explicitly enabled")

    databases = config.get("DATABASES") or {}
    if MOJPROP_DB_ALIAS not in databases:
        blockers.append("DATABASES[mojprop] is not configured")
    else:
        checks.append("dedicated mojprop database alias is configured")
        default_db = databases.get("default")
        if databases.get(MOJPROP_DB_ALIAS) is default_db:
            blockers.append("mojprop database settings must not reuse default settings")

    routers = tuple(config.get("DATABASE_ROUTERS") or ())
    if MOJPROP_ROUTER_IMPORT not in routers:
        blockers.append("fail-closed MojPropDatabaseRouter is not wired in DATABASE_ROUTERS")
    else:
        checks.append("fail-closed MojPropDatabaseRouter is wired")

    identity_secret = str(config.get("MPW_MOJPROP_IDENTITY_DIGEST_SECRET") or "")
    if not identity_secret:
        blockers.append("identity digest secret is not configured for staging")
    else:
        checks.append("identity digest secret is present without logging its value")

    source_alias = str(config.get("MPW_MOJPROP_RECONCILIATION_SOURCE_ALIAS") or "")
    if not source_alias:
        blockers.append("reconciliation source alias is not explicitly configured")
    elif source_alias == MOJPROP_DB_ALIAS:
        blockers.append("reconciliation source alias cannot equal mojprop")
    else:
        checks.append("reconciliation source alias is distinct from mojprop")

    for flag_name in CLOSED_MOJPROP_ROUTE_FLAGS:
        if bool(config.get(flag_name, False)):
            blockers.append(f"{flag_name} must remain false during staging preflight")
        else:
            checks.append(f"{flag_name}=false")

    if migration_admin_verified:
        checks.append("migration administrator evidence supplied")
    else:
        blockers.append("migration administrator privilege evidence is missing")

    if runtime_dml_verified:
        checks.append("runtime DML privilege evidence supplied")
    else:
        blockers.append("runtime DML privilege evidence is missing")

    return StagingPreflight(
        ready=not blockers,
        checks=tuple(checks),
        blockers=tuple(blockers),
    )
