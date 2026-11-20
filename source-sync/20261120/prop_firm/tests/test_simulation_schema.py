import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODELS_PATH = ROOT / "models.py"
MIGRATION_PATH = ROOT / "migrations/0011_simulation_isolation.py"


REQUIRED = {
    "PropSimulationIdentity",
    "PropSimulationInvoiceOwner",
    "PropSimulationAccount",
    "PropSimulationLoginChallenge",
    "PropSimulationEvent",
}


def _classes():
    source = MODELS_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    return source, {
        node.name: node
        for node in tree.body
        if isinstance(node, ast.ClassDef)
    }


def test_required_simulation_models_are_declared():
    _, classes = _classes()
    assert REQUIRED <= classes.keys()


def test_simulation_models_have_no_auth_user_foreign_key():
    source, classes = _classes()
    for name in REQUIRED:
        for node in ast.walk(classes[name]):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr == "ForeignKey":
                    segment = ast.get_source_segment(source, node) or ""
                    assert "auth_user" not in segment


def test_migration_contains_all_isolated_models():
    migration = MIGRATION_PATH.read_text(encoding="utf-8")
    assert '("prop_firm", "0010_reward_reserve_ledger")' in migration
    for name in REQUIRED:
        assert f'name="{name}"' in migration


def test_schema_doc_keeps_release_gates_closed():
    document = (ROOT / "SIMULATION_SCHEMA.md").read_text(encoding="utf-8")
    assert "live invoice route: disabled" in document
    assert "English-only" in document
