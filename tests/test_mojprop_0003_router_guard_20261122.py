"""No real SQL: verify the existing migration 0003 cannot act on default."""
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
import importlib
import hashlib
import types


class Apps:
    def __init__(self):
        self.calls = 0

    def get_model(self, app_label, name):
        self.calls += 1
        if (app_label, name) != ("prop_firm", "PropSimulationPayment"):
            raise AssertionError("wrong model")
        return types.SimpleNamespace(_meta=types.SimpleNamespace(
            db_table="prop_firm_propsimulationpayment"))


class State:
    def __init__(self):
        self.apps = Apps()

    def clear_delayed_apps_cache(self):
        pass


class Editor:
    def __init__(self, alias, exists=False):
        self.events = []
        self.exists = exists
        self.connection = types.SimpleNamespace(
            alias=alias,
            introspection=types.SimpleNamespace(table_names=self.tables))

    def tables(self):
        self.events.append("inspect")
        return ["prop_firm_propsimulationpayment"] if self.exists else []

    def create_model(self, _model):
        self.events.append("create")

    def delete_model(self, _model):
        self.events.append("delete")


class MigrationRouterGuardTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        import django
        django.setup()
        cls.module = importlib.import_module(
            "prop_firm.migrations.0003_payment_table_router_alignment")
        cls.operation = cls.module.Migration(
            "0003_payment_table_router_alignment", "prop_firm").operations[0]

    def execute(self, alias, *, exists=False, reverse=False, override=False):
        editor = Editor(alias, exists)
        state = State()
        fn = (self.operation.database_backwards if reverse
              else self.operation.database_forwards)
        if override:
            with patch("django.db.migrations.operations.special.router.allow_migrate",
                       return_value=True):
                fn("prop_firm", editor, state, state)
        else:
            fn("prop_firm", editor, state, state)
        return editor.events, state.apps.calls

    def test_01_pinned_source(self):
        digest = hashlib.sha256(Path(self.module.__file__).read_bytes()).hexdigest()
        self.assertEqual(
            digest, "1f64de7affb7cbcc050cc7c94ab01c19d0151bc5ba6f1d067fd29707a7122685")

    def test_02_model_hint(self):
        self.assertEqual(self.operation.hints, {"model_name": "propsimulationpayment"})

    def test_03_default_forward(self):
        self.assertEqual(self.execute("default"), ([], 0))

    def test_04_default_reverse(self):
        self.assertEqual(self.execute("default", reverse=True, exists=True), ([], 0))

    def test_05_default_forced_forward(self):
        self.assertEqual(self.execute("default", override=True), ([], 0))

    def test_06_default_forced_reverse(self):
        self.assertEqual(self.execute("default", override=True, reverse=True, exists=True),
                         ([], 0))

    def test_07_other_alias_guard(self):
        self.assertEqual(self.execute("analytics", override=True), ([], 0))

    def test_08_isolated_forward_creates(self):
        self.assertEqual(self.execute("mojprop"), (["inspect", "create"], 1))

    def test_09_isolated_forward_idempotent(self):
        self.assertEqual(self.execute("mojprop", exists=True), (["inspect"], 1))

    def test_10_isolated_reverse_existing(self):
        self.assertEqual(self.execute("mojprop", exists=True, reverse=True),
                         (["inspect", "delete"], 1))

    def test_11_isolated_reverse_absent(self):
        self.assertEqual(self.execute("mojprop", reverse=True), (["inspect"], 1))

    def test_12_uses_real_router(self):
        # CI's global DATABASE_ROUTERS differs between workflow settings.
        # Check the actual production router class without changing CI settings.
        from config.mojprop_db_router import MojPropDatabaseRouter
        production_router = MojPropDatabaseRouter()
        self.assertFalse(production_router.allow_migrate(
            "default", "prop_firm", model_name="propsimulationpayment"))
        self.assertTrue(production_router.allow_migrate(
            "mojprop", "prop_firm", model_name="propsimulationpayment"))
        # Guards in the migration body independently reject default even
        # when the process-wide router has no isolated-app configuration.
        self.assertEqual(self.execute("default", override=True), ([], 0))

    def test_13_two_internal_alias_guards(self):
        src = Path(self.module.__file__).read_text()
        self.assertEqual(src.count(
            "if schema_editor.connection.alias != MOJPROP_DB_ALIAS:"), 2)
