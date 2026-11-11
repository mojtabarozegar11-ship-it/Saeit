"""Regression checks for the offline token gate; no chain access."""
import importlib.util
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("moj_token_supply_guard", Path(__file__).resolve().parents[1] / "scripts" / "moj_token_supply_guard.py")
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def valid_manifest():
    tokens = [{"id": "Mojoner", "chain": "bitcoin", "protocol": "review-pending", "total_supply": "24567856", "owner_approval_id": "example-only"}]
    tokens += [{"id": f"Moj{i}", "chain": "review-pending", "protocol": "review-pending", "total_supply": "100000000000", "owner_approval_id": "example-only"} for i in range(1, 51)]
    return {"tokens": tokens}


def test_complete_manifest_shape():
    assert module.validate(valid_manifest()) == []


def test_duplicate_and_missing_ids_are_blocked():
    manifest = valid_manifest()
    manifest["tokens"][-1] = dict(manifest["tokens"][0])
    assert any("duplicate" in e for e in module.validate(manifest))
    assert any("missing token ids" in e for e in module.validate(manifest))


def test_supply_bounds_and_exact_bitcoin_amount():
    manifest = valid_manifest()
    manifest["tokens"][0]["total_supply"] = "24567857"
    manifest["tokens"][1]["total_supply"] = "99999999999"
    errors = module.validate(manifest)
    assert any("exact supply" in e for e in errors)
    assert any("outside" in e for e in errors)


def test_missing_approval_and_protocol_are_blocked():
    manifest = valid_manifest()
    manifest["tokens"][0]["owner_approval_id"] = ""
    manifest["tokens"][1]["protocol"] = ""
    errors = module.validate(manifest)
    assert any("approval" in e for e in errors)
    assert any("protocol" in e for e in errors)
