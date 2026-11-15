"""C86: Starter30 static assets stay in manual-only release; no hidden writes.

The existing full-repository trigger scanner checks direct push, pull_request
and transitive workflow_run release paths. No deployment, TRON charge, customer
email or real account is created by these tests.
"""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCANNER = ROOT / "tests" / "test_tron_merge_trigger_isolation_20261115.py"
TOUCHED = (
    "scripts/update_mojplaywin_moj_prop_catalog.py",
    "templates/moj-prop-v4/index.html",
    "templates/moj-prop-v4/catalog/index.html",
    "tests/test_mojprop_commercial_samples_release.py",
    "tests/test_mojprop_starter30_public_offer.py",
    "tests/test_mojprop_starter30_atomic_release_no_autodeploy_c86.py",
)


def test_starter30_static_assets_cannot_auto_publish_on_source_merge():
    assert SCANNER.is_file(), "Existing audited workflow scanner is required"
    spec = spec_from_file_location("starter30_c86_workflow_scanner", SCANNER)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    module.SENSITIVE_SOURCE = TOUCHED
    risks = module.find_unapproved_release_paths()
    assert risks == [], "Unexpected automated release path: " + repr(risks[:25])


def test_starter30_static_publication_is_owner_dispatch_only():
    source = (ROOT / ".github/workflows/mojplaywin-moj-prop-deploy.yml").read_text(
        encoding="utf-8"
    )
    assert "github.event_name == 'workflow_dispatch' && inputs.owner_approved_static_release == true" in source
    assert "    runs-on: [self-hosted, factory-vps]" in source
    assert "MOJ_PROP_API_PREFLIGHT=PASS" in source
    assert "MOJ_PROP_STATUS_API_PREFLIGHT=PASS" in source
    assert "scripts/update_mojplaywin_moj_prop_catalog.py deploy" in source
    assert "templates/moj-prop-v4" in source
