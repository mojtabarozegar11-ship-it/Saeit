from unittest.mock import patch

from django.test import TestCase, override_settings

from core.staging_readiness import StagingPreflight, production_action_allowed, validate_acceptance_report


class StagingReadinessTests(TestCase):
    def base_report(self):
        return {
            "environment": "staging", "fixture_provider_count": 0,
            "human_task_creation_count": 0, "manual_stage_advancement_count": 0,
            "external_intermediate_artifact_count": 0, "production_action_successes": 0,
            "published": False, "deployed": False, "lineage_verification": True,
            "launch_candidate_id": "abc", "stages_completed": ["product_launch_candidate"],
        }

    @override_settings(
        SAEIT_ENV="staging", DEBUG=False,
        DATABASES={"default": {"ENGINE": "django.db.backends.postgresql", "NAME": "saeit_production"}},
        STAGING_DB_IDENTITY="saeit_staging", PRODUCTION_DB_IDENTITY="saeit_production",
        PRODUCTION_PUBLICATION_ENABLED=False, REAL_PAYMENTS_ENABLED=False,
        TREASURY_EXECUTION_ENABLED=False, CRYPTO_EXECUTION_ENABLED=False,
        SAEIT_BRIDGE_SECRET="test-signing-only", FACTORY_RESEARCH_PROVIDER="",
        FACTORY_RESEARCH_PROVIDER_TIER="",
    )
    def test_staging_preflight_blocks_production_database_and_missing_provider(self):
        result = StagingPreflight().evaluate()
        self.assertEqual(result.result, "BLOCKED")
        self.assertFalse(result.checks["database_matches_staging_identity"])
        self.assertFalse(result.checks["production_db_not_selected"])
        self.assertFalse(result.checks["provider_configured"])

    @override_settings(SAEIT_ENV="staging")
    def test_staging_blocks_production_actions_and_audits_attempt(self):
        for action in ("publish", "payment_capture", "treasury_transfer", "crypto_transaction"):
            self.assertFalse(production_action_allowed(action))

    def test_report_fails_closed_on_fixture_manual_or_invalid_lineage(self):
        report = self.base_report()
        self.assertTrue(validate_acceptance_report(report))
        for key, value in (
            ("fixture_provider_count", 1), ("human_task_creation_count", 1),
            ("manual_stage_advancement_count", 1), ("external_intermediate_artifact_count", 1),
            ("production_action_successes", 1), ("lineage_verification", False),
            ("published", True), ("deployed", True),
        ):
            invalid = {**report, key: value}
            self.assertFalse(validate_acceptance_report(invalid))

    @override_settings(
        SAEIT_ENV="staging", DEBUG=False,
        DATABASES={"default": {"ENGINE": "django.db.backends.postgresql", "NAME": "saeit_staging"}},
        STAGING_DB_IDENTITY="saeit_staging", PRODUCTION_DB_IDENTITY="saeit_production",
        PRODUCTION_PUBLICATION_ENABLED=True, REAL_PAYMENTS_ENABLED=True,
        TREASURY_EXECUTION_ENABLED=True, CRYPTO_EXECUTION_ENABLED=True,
        SAEIT_BRIDGE_SECRET="test-signing-only", FACTORY_RESEARCH_PROVIDER="x.Provider",
        FACTORY_RESEARCH_PROVIDER_TIER="fixture",
    )
    def test_preflight_blocks_production_switches_and_fixture_tier(self):
        with patch("core.staging_readiness.connection.ensure_connection"), patch(
            "core.staging_readiness.MigrationExecutor"
        ) as executor:
            executor.return_value.migration_plan.return_value = []
            executor.return_value.loader.graph.leaf_nodes.return_value = []
            result = StagingPreflight().evaluate()
        self.assertEqual(result.result, "BLOCKED")
        self.assertFalse(result.checks["publication_disabled"])
        self.assertFalse(result.checks["payments_disabled"])
        self.assertFalse(result.checks["treasury_disabled"])
        self.assertFalse(result.checks["crypto_disabled"])
        self.assertFalse(result.checks["provider_tier_real_staging_safe"])
        self.assertFalse(result.checks["provider_not_fixture"])
