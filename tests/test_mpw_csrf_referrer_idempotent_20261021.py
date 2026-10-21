"""Offline tests: no existing customer form should be overwritten blindly."""
import importlib.util
from pathlib import Path

SOURCE=Path(__file__).resolve().parents[1]/"scripts/mpw_customer_csrf_referrer_repair_20261021.py"
spec=importlib.util.spec_from_file_location("mpw_customer_referrer",SOURCE)
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

def form(policy):
    return ('<html><head><meta name="referrer" content="'+policy+'"></head>'
            '<body><form method="post">{% csrf_token %}</form></body></html>').encode()

def test_verified_existing_same_origin_policy_is_a_safe_noop():
    assert mod.classify_template(form("same-origin"))=="already_fixed"

def test_old_policy_is_detected_for_gated_repair():
    assert mod.classify_template(form("no-referrer"))=="needs_patch"

def test_ambiguous_and_duplicate_policies_are_rejected():
    assert mod.classify_template(form("strict-origin"))=="unverifiable"
    assert mod.classify_template(form("same-origin")+mod.NEW.encode())=="unverifiable"
    assert mod.classify_template(form("no-referrer")+mod.NEW.encode())=="unverifiable"

def test_workflow_inspects_first_and_skips_repeat_install():
    flow=(SOURCE.parents[1]/".github/workflows/mpw-customer-mobile-csrf-cookie-fresh-live-20261020.yml").read_text()
    assert "MPW_CSRF_TEMPLATE_STATE=" in flow
    assert "if: steps.inspect.outputs.state == 'needs_patch'" in flow
    assert flow.index("Inspect existing CSRF template state")<flow.index("Install same-origin referrer")
