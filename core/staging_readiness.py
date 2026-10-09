"""Fail-closed policy for isolated real-staging autonomy acceptance."""
import hashlib
import json
import os
from dataclasses import dataclass

from django.conf import settings
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from .factory_agent_runtime import FixtureResearchProvider, configured_research_provider
from .models import AuditLog


PROVIDER_CLASSES = {
    "fixture": "FIXTURE/CI-ONLY",
    "sandbox": "SANDBOX",
    "staging": "REAL-STAGING-SAFE",
    "production": "PRODUCTION-ONLY",
}


def environment_name():
    return str(getattr(settings, "SAEIT_ENV", "") or "").strip().lower()


def production_action_allowed(action):
    if environment_name() == "staging":
        AuditLog.objects.create(
            actor_type="system", actor_id="staging-policy", action="staging_production_action_blocked",
            target_type="policy", target_id=str(action), after_state={"allowed": False, "environment": "staging"},
            trace_id=f"staging-block-{hashlib.sha256(str(action).encode()).hexdigest()[:16]}",
        )
        return False
    return environment_name() == "production"


@dataclass(frozen=True)
class StagingPreflightResult:
    result: str
    checks: dict
    blockers: tuple

    def as_dict(self):
        return {"environment": environment_name(), "result": self.result,
                "checks": self.checks, "blockers": list(self.blockers)}


class StagingPreflight:
    def evaluate(self):
        checks, blockers = {}, []

        def check(name, ok, reason):
            checks[name] = bool(ok)
            if not ok:
                blockers.append(reason)

        check("environment_is_staging", environment_name() == "staging", "SAEIT_ENV must be staging.")
        check("debug_disabled", settings.DEBUG is False, "DEBUG must be False for real staging acceptance.")
        db = settings.DATABASES["default"]
        db_name = str(db.get("NAME") or "")
        staging_identity = str(getattr(settings, "STAGING_DB_IDENTITY", "") or "").strip()
        production_identity = str(getattr(settings, "PRODUCTION_DB_IDENTITY", "") or "").strip()
        check("staging_db_identity_configured", bool(staging_identity), "STAGING_DB_IDENTITY is required.")
        check("database_matches_staging_identity", bool(staging_identity and staging_identity == db_name),
              "Configured database does not match STAGING_DB_IDENTITY.")
        check("production_db_not_selected", bool(production_identity) and production_identity != db_name,
              "Staging database appears to match PRODUCTION_DB_IDENTITY.")
        check("database_not_sqlite", db.get("ENGINE") == "django.db.backends.postgresql",
              "Real staging acceptance requires an isolated non-SQLite database.")
        check("publication_disabled", not getattr(settings, "PRODUCTION_PUBLICATION_ENABLED", False),
              "Production publication must be disabled in staging.")
        check("payments_disabled", not getattr(settings, "REAL_PAYMENTS_ENABLED", False),
              "Real payments must be disabled in staging.")
        check("treasury_disabled", not getattr(settings, "TREASURY_EXECUTION_ENABLED", False),
              "Treasury execution must be disabled in staging.")
        check("crypto_disabled", not getattr(settings, "CRYPTO_EXECUTION_ENABLED", False),
              "Crypto execution must be disabled in staging.")
        check("bridge_signing_configured", bool(getattr(settings, "SAEIT_BRIDGE_SECRET", "")),
              "SAEIT_BRIDGE_SECRET is required for authenticated staging execution.")
        provider_class = str(getattr(settings, "FACTORY_RESEARCH_PROVIDER", "") or "").strip()
        provider_tier = str(getattr(settings, "FACTORY_RESEARCH_PROVIDER_TIER", "") or "").strip().lower()
        check("provider_configured", bool(provider_class), "A staging research provider is required.")
        check("provider_tier_real_staging_safe", provider_tier == "staging",
              "FACTORY_RESEARCH_PROVIDER_TIER must be staging (REAL-STAGING-SAFE).")
        provider_ok = False
        if provider_class and provider_tier == "staging":
            try:
                provider = configured_research_provider()
                provider_ok = getattr(provider, "real_research", False) is True and not isinstance(provider, FixtureResearchProvider)
            except Exception:
                provider_ok = False
        check("provider_not_fixture", provider_ok, "Real staging acceptance cannot use fixture/non-real research.")
        try:
            connection.ensure_connection()
            migrations_ok = not MigrationExecutor(connection).migration_plan(
                MigrationExecutor(connection).loader.graph.leaf_nodes()
            )
        except Exception:
            migrations_ok = False
        check("database_connectivity_and_migrations", migrations_ok,
              "Staging database must be reachable with all migrations applied.")
        try:
            audit_ok = AuditLog.objects.order_by("-pk").values_list("pk", flat=True).first() is not None or True
        except Exception:
            audit_ok = False
        check("audit_logging_available", audit_ok, "Audit logging/database access is unavailable.")
        from .models import Agent, AgentToolGrant
        from .management.commands.seed_factory_agents import SPECIALISTS
        from django.utils import timezone
        try:
            available = Agent.objects.filter(code="factory-master-agent", active=True).exists() and all(
                AgentToolGrant.objects.filter(agent__code=agent[0], agent__active=True,
                    capability_code=action, tool_code=action, environment="staging", active=True,
                    revoked_at__isnull=True, valid_until__gt=timezone.now()).exists()
                for action, agent in SPECIALISTS.items())
        except Exception:
            available = False
        check("master_worker_available", available, "Staging Master/specialist grants missing or expired.")
        return StagingPreflightResult("PASS" if not blockers else "BLOCKED", checks, tuple(blockers))


REQUIRED_STAGES = (
    "product_research", "product_opportunity_score", "product_validation", "product_spec",
    "product_build_record", "product_test", "product_security", "product_localize",
    "product_market_eligibility", "product_qa", "product_launch_candidate",
)


def validate_acceptance_report(report):
    required_zero = ("fixture_provider_count", "human_task_creation_count",
                     "manual_stage_advancement_count", "external_intermediate_artifact_count",
                     "production_action_successes")
    if report.get("environment") != "staging":
        return False
    if any(type(report.get(key)) is not int or report[key] != 0 for key in required_zero):
        return False
    if report.get("published") is not False or report.get("deployed") is not False:
        return False
    if report.get("lineage_verification") is not True or report.get("real_source_provenance") is not True:
        return False
    if not report.get("launch_candidate_id") or not report.get("providers_used"):
        return False
    stages = report.get("stages_completed", [])
    if any(stage not in stages for stage in REQUIRED_STAGES):
        return False
    if [stages.index(stage) for stage in REQUIRED_STAGES] != sorted(stages.index(stage) for stage in REQUIRED_STAGES):
        return False
    identities = report.get("independent_verifier_identities", {})
    names = [identities.get(key) for key in ("product_validation", "product_test", "product_security", "product_qa")]
    return all(names) and len(set(names)) == 4 and report.get("builder_identity") not in names
