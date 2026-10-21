"""Offline regression for public customer-form CSRF policy diagnostics."""
import importlib.util
from pathlib import Path

SOURCE=Path(__file__).resolve().parents[1]/"scripts/mpw_registration_csrf_public_probe_20261021.py"
spec=importlib.util.spec_from_file_location("mpw_csrf_probe",SOURCE)
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_meta_no_referrer_is_detected_not_silently_missed():
    markup='<html><head><meta name="referrer" content="no-referrer"></head></html>'
    assert mod.REFERRER_META_RE.search(markup)


def test_safe_referrer_is_not_falsely_reported_as_blocked():
    markup='<html><head><meta name="referrer" content="same-origin"></head></html>'
    assert mod.REFERRER_META_RE.search(markup) is None


def test_single_quote_and_case_variation_are_recognized():
    markup="<meta NAME='referrer' CONTENT='no-referrer'>"
    assert mod.REFERRER_META_RE.search(markup)
