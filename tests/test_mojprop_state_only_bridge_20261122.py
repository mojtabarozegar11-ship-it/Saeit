"""Contract for two immutable prop_firm migration histories. No database writes."""
import ast
import hashlib
import json
import os
from pathlib import Path
from unittest import TestCase

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "prop_firm" / "migrations"
ARCHIVE = ROOT / "source-sync" / "20261120" / "prop_firm" / "migrations"
PINNED = ROOT / "tests" / "mojprop_historical_migration_blobs_20261122.json"
BRIDGE = MIGRATIONS / "0011_state_only_bridge.py"
OLD_MODELS = {
    "PropTrader", "PropAccount", "PropExecution", "PropEquityObservation",
    "PropDecisionLog", "PropProfitAllocation", "PropProfitJournalLine",
    "PropSocialEvidence", "PropChallengeEnrollment", "PropInterest",
    "TronSettlementLedger", "PropPlan1Invoice", "PropPlan1Receipt",
    "PropRewardReserveAllocation", "PropRewardCommitment",
}
NEW_MODELS = {
    "propsimulationidentity", "propsimulationinvoiceowner", "propsimulationaccount",
    "propsimulationloginchallenge", "propsimulationevent",
    "propsimulationpayment", "propsimulationpayoutcommitment",
}


def git_blob(path):
    payload = path.read_bytes()
    return hashlib.sha1(
        b"blob " + str(len(payload)).encode() + b"\0" + payload).hexdigest()


class StateOnlyBridgeTests(TestCase):
    def test_01_exact_historical_archive_bytes(self):
        pins = json.loads(PINNED.read_text(encoding="utf-8"))
        self.assertEqual(len(pins), 10)
        for name, expected in pins.items():
            for parent in (ARCHIVE, MIGRATIONS):
                file = parent / (name + ".py")
                self.assertTrue(file.is_file(), str(file))
                self.assertEqual(git_blob(file), expected, str(file))

    def test_02_archived_duplicate_0011_not_installed(self):
        self.assertTrue((ARCHIVE / "0011_simulation_isolation.py").is_file())
        self.assertFalse((MIGRATIONS / "0011_simulation_isolation.py").exists())

    def test_03_exact_bridge_dependencies_and_no_ddl(self):
        import importlib
        import django
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
        django.setup()
        module = importlib.import_module("prop_firm.migrations.0011_state_only_bridge")
        migration = module.Migration("0011_state_only_bridge", "prop_firm")
        self.assertEqual(set(migration.dependencies), {
            ("prop_firm", "0010_reward_reserve_ledger"),
            ("prop_firm", "0006_unique_invoice_receivers"),
        })
        self.assertEqual(len(migration.operations), 1)
        op = migration.operations[0]
        self.assertEqual(op.database_operations, [])
        self.assertEqual(len(op.state_operations), 15)
        self.assertEqual({x.name for x in op.state_operations}, OLD_MODELS)

    def test_04_receiver_unique_migration_is_pinned(self):
        self.assertEqual(git_blob(MIGRATIONS / "0006_unique_invoice_receivers.py"),
                         "90c2af4c2ac813a3bed7279d695b72970c1e10f9")

    def test_05_graph_has_one_leaf(self):
        import django
        from django.db.migrations.loader import MigrationLoader
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
        django.setup()
        loader = MigrationLoader(None, ignore_no_migrations=True)
        leaves = [name for app, name in loader.graph.leaf_nodes() if app == "prop_firm"]
        self.assertEqual(leaves, ["0011_state_only_bridge"])

    def test_06_final_state_is_only_seven_simulation_models(self):
        import django
        from django.db.migrations.loader import MigrationLoader
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
        django.setup()
        loader = MigrationLoader(None, ignore_no_migrations=True)
        state = loader.project_state([("prop_firm", "0011_state_only_bridge")])
        names = {name for app, name in state.models if app == "prop_firm"}
        self.assertEqual(names, NEW_MODELS)
        self.assertTrue(state.models[
            ("prop_firm", "propsimulationpayment")].fields["recipient"].unique)

    def test_07_no_destructive_db_operation_in_bridge(self):
        src = BRIDGE.read_text(encoding="utf-8")
        for forbidden in ("RunSQL(", "RunPython(", "CreateModel(", "schema_editor",
                          "issue_invoice(", "settle_invoice(", "payment.transfer("):
            self.assertNotIn(forbidden, src)
