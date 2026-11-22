from django.test import SimpleTestCase

from config.mojprop_db_router import MOJPROP_DB_ALIAS, MojPropDatabaseRouter
from prop_firm.models import PropSimulationStageTransition


class SimulationStageTransitionRouterTests(SimpleTestCase):
    def test_stage_transition_is_read_write_and_migration_routed_to_isolated_alias(self):
        router = MojPropDatabaseRouter()
        self.assertEqual(router.db_for_read(PropSimulationStageTransition), MOJPROP_DB_ALIAS)
        self.assertEqual(router.db_for_write(PropSimulationStageTransition), MOJPROP_DB_ALIAS)
        self.assertTrue(
            router.allow_migrate(
                MOJPROP_DB_ALIAS,
                "prop_firm",
                "propsimulationstagetransition",
                model=PropSimulationStageTransition,
            )
        )

    def test_stage_transition_is_not_allowed_on_default_database(self):
        router = MojPropDatabaseRouter()
        self.assertFalse(
            router.allow_migrate(
                "default",
                "prop_firm",
                "propsimulationstagetransition",
                model=PropSimulationStageTransition,
            )
        )
