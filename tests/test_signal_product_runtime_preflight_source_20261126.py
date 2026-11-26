from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/mpw_signal_product_runtime_preflight_20261126.py"
SOURCE = SCRIPT.read_text(encoding="utf-8")


def test_product_preflight_is_read_only_and_fail_closed():
    assert '"read_only": True' in SOURCE
    assert '"public_signal_subscription_enabled": False' in SOURCE
    assert '"public_sale_changed": False' in SOURCE
    assert 'Product.objects.filter(metadata__signal_plan_id=plan_id)' in SOURCE
    assert "objects.create(" not in SOURCE
    assert ".save(" not in SOURCE
    assert ".delete(" not in SOURCE
    assert "migrate --" not in SOURCE
