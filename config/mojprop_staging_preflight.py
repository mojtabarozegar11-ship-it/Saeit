"""Pure preflight for root-runtime MOJ PROP staging configuration."""

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
    ready: bool
    checks: tuple[str, ...]
    blockers: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {"ready": self.ready, "checks": list(self.checks), "blockers": list(self.blockers)}


def evaluate_staging_preflight(config: Mapping[str, Any], *, migration_admin_verified=False, runtime_dml_verified=False):
    checks = []
    blockers = []
    if not bool(config.get("MPW_MOJPROP_DB_ALIAS_ENABLED", False)):
        blockers.append("MOJ PROP database alias switch is not enabled for staging")
    else:
        checks.append("MOJ PROP database alias switch is explicitly enabled")
    databases = config.get("DATABASES") or {}
    if MOJPROP_DB_ALIAS not in databases:
        blockers.append("DATABASES[mojprop] is not configured")
    else:
        checks.append("dedicated mojprop database alias is configured")
        if databases.get(MOJPROP_DB_ALIAS) is databases.get("default"):
            blockers.append("mojprop database settings must not reuse default settings")
    if MOJPROP_ROUTER_IMPORT not in tuple(config.get("DATABASE_ROUTERS") or ()):
        blockers.append("fail-closed MojPropDatabaseRouter is not wired in DATABASE_ROUTERS")
    else:
        checks.append("fail-closed MojPropDatabaseRouter is wired")
    if not str(config.get("MPW_MOJPROP_IDENTITY_DIGEST_SECRET") or ""):
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
    for flag in CLOSED_MOJPROP_ROUTE_FLAGS:
        if bool(config.get(flag, False)):
            blockers.append(f"{flag} must remain false during staging preflight")
        else:
            checks.append(f"{flag}=false")
    if migration_admin_verified:
        checks.append("migration administrator evidence supplied")
    else:
        blockers.append("migration administrator privilege evidence is missing")
    if runtime_dml_verified:
        checks.append("runtime DML privilege evidence supplied")
    else:
        blockers.append("runtime DML privilege evidence is missing")
    return StagingPreflight(not blockers, tuple(checks), tuple(blockers))
