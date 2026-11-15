"""Fail-closed release audit for the buyer-facing Moj Prop price-draft change.

Reuse the independently CI-verified all-workflow reachability scanner on the
exact current diff. This runs offline and does not dispatch an action, release
a site, send email, or access wallets.
"""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tests" / "test_tron_merge_trigger_isolation_20261115.py"
TOUCHED = (
    "core/mojprop_offer_draft.py",
    "tests/test_mojprop_signal_offer_price_integrity_20261115.py",
    "tests/test_mojprop_signal_offer_no_autodeploy_20261115.py",
)


def test_offer_draft_merge_cannot_invoke_unattended_release():
    assert SOURCE.is_file(), "Proven workflow scanner is required"
    spec = spec_from_file_location("verified_release_scanner_c84", SOURCE)
    assert spec and spec.loader
    scanner = module_from_spec(spec)
    spec.loader.exec_module(scanner)
    scanner.SENSITIVE_SOURCE = TOUCHED
    risks = scanner.find_unapproved_release_paths()
    assert risks == [], "Unexpected workflow write path for this source change: " + repr(risks[:25])
