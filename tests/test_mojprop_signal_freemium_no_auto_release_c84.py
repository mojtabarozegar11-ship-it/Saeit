"""No auto-release from source-only single-bot free/paid proposal changes."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCAN = ROOT / "tests/test_tron_merge_trigger_isolation_20261115.py"
CHANGED = (
    "core/mojprop_offer_draft.py",
    "core/test_mojprop_offer_draft_command.py",
    "tests/test_mojprop_signal_freemium_price_integrity_c84.py",
    "tests/test_mojprop_signal_freemium_no_auto_release_c84.py",
)


def test_freemium_price_integrity_merge_has_no_unattended_release():
    assert SCAN.is_file(), "Verified release-isolation scanner is required"
    spec = spec_from_file_location("mojprop_freemium_release_scanner", SCAN)
    assert spec is not None and spec.loader is not None
    mod = module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.SENSITIVE_SOURCE = CHANGED
    paths = mod.find_unapproved_release_paths()
    assert not paths, "Source merge may trigger unattended writes: " + repr(paths[:25])
