import ast
from pathlib import Path


ROUTER_PATH = Path(__file__).resolve().parents[2] / "config/mojprop_db_router.py"


def test_router_is_fail_closed_for_the_dedicated_alias():
    source = ROUTER_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    names = {node.name for node in tree.body if isinstance(node, ast.ClassDef)}
    assert "MojPropDatabaseRouter" in names
    assert "MOJPROP_DB_ALIAS = \"mojprop\"" in source
    assert "return label in ISOLATED_MODEL_LABELS" in source


def test_router_blocks_isolated_models_on_default_database():
    source = ROUTER_PATH.read_text(encoding="utf-8")
    assert "if label in ISOLATED_MODEL_LABELS:" in source
    assert "return False" in source
