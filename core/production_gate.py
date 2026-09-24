from django.conf import settings
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.db.utils import OperationalError

from .health_gate import RuntimeHealthGate


class ProductionGate:
    """Read-only final gate for production startup/deployment validation."""

    def __init__(self, health_gate=None):
        self.health_gate = health_gate or RuntimeHealthGate()

    def evaluate(self, *, stale_after_seconds=900, max_failed=0, max_stale=0):
        checks = {}
        reasons = []

        checks["debug_disabled"] = settings.DEBUG is False
        if not checks["debug_disabled"]:
            reasons.append("DEBUG must be False")

        checks["secret_key_configured"] = bool(settings.SECRET_KEY) and settings.SECRET_KEY != "change-me"
        if not checks["secret_key_configured"]:
            reasons.append("SECRET_KEY is not safely configured")

        checks["allowed_hosts_configured"] = bool(settings.ALLOWED_HOSTS)
        if not checks["allowed_hosts_configured"]:
            reasons.append("ALLOWED_HOSTS is empty")

        try:
            connection.ensure_connection()
            checks["database"] = True
        except Exception:
            checks["database"] = False
            reasons.append("database connection failed")

        if checks["database"]:
            try:
                executor = MigrationExecutor(connection)
                plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
                checks["migrations_current"] = not bool(plan)
                if not checks["migrations_current"]:
                    reasons.append("pending migrations detected")
            except Exception:
                checks["migrations_current"] = False
                reasons.append("migration state could not be verified")
        else:
            checks["migrations_current"] = False
            reasons.append("migration state unavailable because database is unavailable")

        runtime = self.health_gate.evaluate(
            stale_after_seconds=stale_after_seconds,
            max_failed=max_failed,
            max_stale=max_stale,
        )
        checks["runtime_health"] = runtime.healthy
        reasons.extend(runtime.reasons)

        return type("ProductionGateResult", (), {
            "ready": not reasons,
            "checks": checks,
            "reasons": tuple(reasons),
        })()
